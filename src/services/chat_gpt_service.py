import base64
import csv
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

import discord
from openai import AsyncOpenAI

from env import CHAT_GPT_API_KEY
from utilities.constants import MESSAGE_HISTORY_CHANNELS

client = AsyncOpenAI(
    api_key=CHAT_GPT_API_KEY
)

BASE_DIR = Path(__file__).resolve().parent.parent
MAX_DAYS = 30
MAX_HOURS = 720
MAX_TOTAL_HOURS = 1080
MESSAGE_HISTORY_FILE = BASE_DIR / "resources" / "server_atrocious_messages.txt"
MESSAGE_HISTORY_FILE_2025 = BASE_DIR / "resources" / "server_atrocious_messages_2025.txt"
MESSAGE_HISTORY_FILE_SUMMARIZED = BASE_DIR / "resources" / "server_atrocious_messages_summarized.txt"
MIDNIGHT_GUIDE_RESOURCES = BASE_DIR / "resources" / "midnight_raider_guide_files"
STATE_FILE = BASE_DIR / "resources" / "last_message_ids.json"
WORD_LIMIT = 40000


async def get_chat_gpt_response(message: discord.Message, bot: discord.Client):
    # Read summarized message history for context
    try:
        with open(MESSAGE_HISTORY_FILE_SUMMARIZED, "r", encoding="utf-8") as f:
            message_history_context = f.read()
    except FileNotFoundError:
        message_history_context = ""

    clean_prompt = clean_message_content(message, bot)

    # Build system prompt
    system_prompt = """
    Follow these directions:
    - One of your hobbies is doing Mythic Raiding and Mythic+ in World of Warcraft.
    - If the questions is not about World of Warcraft, give a standard response.
    - Keep responses under 250 words.
    - Match sarcasm/memes if the user uses them.
    - Tastefully mock users when they ask something against guidelines.
    - No excessive "!" usage.
    - Never start responses with "Haha,".
    - Pick a random WoW character if asked about your origin.
    """

    # Replied message text (quote)
    reply_text = await get_replied_text(message)

    # --------- Build Base Prompt Text ----------
    if reply_text:
        text_prompt = (
            f"System Prompt: {system_prompt}\n"
            f"Message History Context: {message_history_context}\n"
            f"Quote: {reply_text}\n"
            f"User Prompt: {clean_prompt}"
        )
    else:
        text_prompt = (
            f"System Prompt: {system_prompt}\n"
            f"Message History Context: {message_history_context}\n"
            f"User Prompt: {clean_prompt}"
        )

    # --------- CHECK IF THE USER SENT AN IMAGE ----------
    has_image = False
    image_urls = []

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            has_image = True
            image_urls.append(attachment.url)

    # ======================================================
    #  IF IMAGE → USE GPT-4o VISION (chat.completions)
    # ======================================================
    if has_image:
        vision_inputs = [
            {"type": "text", "text": text_prompt}
        ]

        # Add each image to the input
        for url in image_urls:
            vision_inputs.append({
                "type": "image_url",
                "image_url": {"url": url}
            })

        response = await client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "user", "content": vision_inputs}
            ],
        )

        # This replaces the word "ladder" with "climbing device" from the response (for the memes)
        return re.sub(r'(?i)l\s*a\s*d\s*d\s*e\s*r', "climbing device", response.choices[0].message.content[:2000])

    # ======================================================
    #  OTHERWISE → NORMAL TEXT MODE WITH BROWSING
    # ======================================================
    response = await client.responses.create(
        model="gpt-5.2",
        input=text_prompt,
        store=False,
    )

    # This replaces the word "ladder" with "climbing device" from the response (for the memes)
    return re.sub(r'(?i)l\s*a\s*d\s*d\s*e\s*r', "climbing device", response.output_text[:2000])


async def summarize_file():
    # Read the file
    with open(MESSAGE_HISTORY_FILE_2025, "r", encoding="utf-8") as f:
        file_text = f.read()

    # Ask the AI to summarize under 5000 words
    prompt = (
            "Summarize the following text in under 5000 words. "
            "The output should be organized so you can fetch information based on the users' names and so you get a sense of the "
            "personality of each user:\n\n" + file_text
    )

    response = await client.responses.create(
        model="gpt-5-nano",
        input=prompt,
        store=False,
    )

    # Write the summary to a new file
    with open(MESSAGE_HISTORY_FILE_SUMMARIZED, "w", encoding="utf-8") as f:
        f.write(response.output_text)


def clean_message_content(message: discord.Message, bot: discord.Client) -> str:
    content = message.content

    # Replace "ladder" with "climbing device" (for the memes)
    content = re.sub(r'(?i)l\s*a\s*d\s*d\s*e\s*r', "climbing device", content)

    # Remove the bot mention entirely
    content = content.replace(f"<@{bot.user.id}>", "")
    content = content.replace(f"<@!{bot.user.id}>", "")  # handles mobile-style mentions too

    # Replace all other user mentions (<@12345>) with their username
    for user in message.mentions:
        content = content.replace(f"<@{user.id}>", f"{user.display_name}")
        content = content.replace(f"<@!{user.id}>", f"{user.display_name}")

    # Replace role mentions (<@&12345>) with their role name
    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")

    # Replace channel mentions (<#12345>) with their channel name
    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")

    # Clean up extra spaces
    return content.strip()


async def get_replied_text(message: discord.Message) -> str | None:
    """Return the content of the message being replied to, if any."""
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        # The referenced message is already resolved (cached)
        return message.reference.resolved.content

    elif message.reference:
        # If not resolved, fetch it from Discord
        try:
            replied_msg = await message.channel.fetch_message(message.reference.message_id)
            return replied_msg.content
        except discord.NotFound:
            return None
        except discord.Forbidden:
            return None
        except discord.HTTPException:
            return None

    return None


async def scrape_server_message_history(bot):
    with open(MESSAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
        for channel_id in MESSAGE_HISTORY_CHANNELS:
            channel = bot.get_channel(channel_id)

            if not isinstance(channel, discord.TextChannel):
                logging.info(f"Skipping {channel_id}: not a TextChannel or inaccessible.")
                continue

            logging.info(f"Fetching messages from #{channel.name} ({channel.id})...")

            # Fetch messages from oldest to newest
            async for message in channel.history(limit=None, oldest_first=True):
                content = message.clean_content.strip()

                if not content:
                    continue  # skip empty messages

                f.write(f"[{message.created_at}] {message.author}: {content}\n")

    logging.info(f"All messages saved to {MESSAGE_HISTORY_FILE}")


async def update_message_history(bot: discord.Client):
    # Fetch new messages since the last saved message ID for each channel, and append them to the text file.
    # Load last message IDs
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            last_message_ids = json.load(f)
    else:
        last_message_ids = {}

    with open(MESSAGE_HISTORY_FILE, "a", encoding="utf-8") as f:
        for channel_id in MESSAGE_HISTORY_CHANNELS:
            channel = bot.get_channel(channel_id)

            if not isinstance(channel, discord.TextChannel):
                logging.info(f"Skipping {channel_id}: not a TextChannel or inaccessible.")
                continue

            last_id = last_message_ids.get(str(channel_id))
            after_obj = discord.Object(id=last_id) if last_id else None
            logging.info(f"Checking for new messages in #{channel.name} ({channel.id})...")

            new_last_id = last_id
            async for message in channel.history(limit=None, after=after_obj, oldest_first=True):
                content = message.clean_content.strip()
                if not content:
                    continue
                f.write(f"[{message.created_at}] {message.author}: {content}\n")
                new_last_id = message.id  # update each time we see a newer message

            if new_last_id:
                last_message_ids[str(channel_id)] = new_last_id

    # Save updated last IDs
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(last_message_ids, f, indent=2)

    logging.info("Hourly message update complete.")


async def get_channel_history_by_days(interaction: discord.Interaction, days: int, hours: int) -> str:
    """
    Scrape messages from the channel where the interaction occurred,
    bounded by time (days → hours), per-message size, and total word count.

    Returns a single formatted string suitable for LLM input.
    """

    # ---- Clamp days and calculate cutoff ----
    days = max(0, min(days, MAX_DAYS))
    hours = max(0, min(hours, MAX_HOURS))
    total_hours = max(1, min(hours + days * 24, MAX_TOTAL_HOURS))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=total_hours)

    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        logging.info("Interaction channel is not a text channel.")
        return ""

    messages = []

    # ---- Fetch messages (oldest → newest) ----
    async for message in channel.history(limit=None, oldest_first=True, after=cutoff):
        content = message.clean_content.strip()

        if not content:
            continue

        formatted = (
            f"[{message.created_at:%Y-%m-%d %H:%M}] "
            f"{message.author.display_name}: {content}"
        )

        messages.append(formatted)

    # ---- Trim to total WORD_LIMIT (newest-first) ----
    selected = []
    total_words = 0

    for msg in reversed(messages):
        msg_words = count_words(msg)

        if total_words + msg_words > WORD_LIMIT:
            break

        selected.append(msg)
        total_words += msg_words

    selected.reverse()

    logging.info(
        f"Scraped {len(selected)} messages "
        f"from last {hours} hours "
        f"({total_words} words)"
    )

    return "\n".join(selected)


def count_words(text: str) -> int:
    return len(text.split())


async def generate_midnight_guide_response(user_question: str):
    guide = retrieve_midnight_guide_context()

    # Prepare GPT messages
    messages = [
        {
            "role": "system",
            "content": [
                {"type": "text", "text": "You are a World of Warcraft Midnight expansion raid guide assistant. Do not mention the file(s) you get the data from."}
            ]
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"The user asked: {user_question}"},
                {"type": "text", "text": f"Text Guide:\n{guide['text_guide']}"},
                {"type": "text", "text": f"Weekly Checklist: {json.dumps(guide['checklist'], ensure_ascii=False)}"}
            ]
        }
    ]

    # Include item-level CSVs
    for csv_name, rows in guide["item_levels"].items():
        messages[1]["content"].append({
            "type": "text",
            "text": f"{csv_name}: {json.dumps(rows, ensure_ascii=False)}"
        })

    # Call GPT‑5.2
    response = await client.chat.completions.create(
        model="gpt-5.2",
        messages=messages
    )

    return response.choices[0].message.content


def retrieve_midnight_guide_context():
    guide_data = {}

    # Load text guide
    txt_path = os.path.join(MIDNIGHT_GUIDE_RESOURCES, "midnight_raider_guide.txt")

    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            guide_data["text_guide"] = f.read()
    else:
        guide_data["text_guide"] = "Guide text file not found."

    # Load weekly checklist CSV
    checklist_path = os.path.join(MIDNIGHT_GUIDE_RESOURCES, "weekly_midnight_checklist.csv")
    checklist_items = []

    if os.path.exists(checklist_path):
        with open(checklist_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                checklist_items.append(row)

    guide_data["checklist"] = checklist_items

    # Load all item-level CSVs
    item_level_csvs = [
        "midnight_gear_data_1.csv",
        "midnight_gear_data_2.csv",
        "midnight_gear_data_3.csv",
        "midnight_gear_data_4.csv",
        "midnight_gear_data_5.csv",
        "midnight_gear_data_6.csv",
        "midnight_gear_data_7.csv",
    ]
    item_level_data = {}

    for csv_file in item_level_csvs:
        path = os.path.join(MIDNIGHT_GUIDE_RESOURCES, csv_file)
        rows = []

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    rows.append(row)

        item_level_data[csv_file] = rows
    guide_data["item_levels"] = item_level_data

    print(guide_data)

    return guide_data
