import json
import logging
import os
import random
from pathlib import Path

import discord
from openai import AsyncOpenAI

from env import CHAT_GPT_API_KEY
from utilities.constants import MESSAGE_HISTORY_CHANNELS

client = AsyncOpenAI(
    api_key=CHAT_GPT_API_KEY
)
BASE_DIR = Path(__file__).resolve().parent.parent

MESSAGE_HISTORY_FILE = BASE_DIR / "resources" / "server_atrocious_messages.txt"
MESSAGE_HISTORY_FILE_2025 = BASE_DIR / "resources" / "server_atrocious_messages_2025.txt"
MESSAGE_HISTORY_FILE_SUMMARIZED = BASE_DIR / "resources" / "server_atrocious_messages_summarized.txt"
STATE_FILE = BASE_DIR / "resources" / "last_message_ids.json"


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
    - By default, give a normal response.
    - One of your hobbies is doing Mythic Raiding and Mythic+ in World of Warcraft.
    - Keep responses under 250 words.
    - Match sarcasm/memes if the user uses them.
    - Tastefully mock users when they ask something against guidelines.
    - No excessive "!" usage.
    - Never start responses with "Haha,".
    - Pick a random WoW character if asked about your origin.
    - Be neutral/nice sometimes.
    - DO NOT use the word "ladder".
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
            model="gpt-4o",
            messages=[
                {"role": "user", "content": vision_inputs}
            ],
            temperature=round(max(0.0, min(2.0, random.gauss(1.0, 0.4))), 1),
            top_p=round(max(0.0, min(1.0, random.gauss(0.5, 0.2))), 1),
        )

        return response.choices[0].message["content"][:1750]

    # ======================================================
    #  OTHERWISE → NORMAL TEXT MODE WITH BROWSING
    # ======================================================
    response = await client.responses.create(
        model="gpt-4o",
        input=text_prompt,
        temperature=round(max(0.0, min(2.0, random.gauss(1.0, 0.4))), 1),
        top_p=round(max(0.0, min(1.0, random.gauss(0.5, 0.2))), 1),
        store=False,
        tools=[{"type": "web_search_preview_2025_03_11"}]
    )

    return response.output_text[:1750]



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

    # 1️⃣ Remove the bot mention entirely
    content = content.replace(f"<@{bot.user.id}>", "")
    content = content.replace(f"<@!{bot.user.id}>", "")  # handles mobile-style mentions too

    # 2️⃣ Replace all other user mentions (<@12345>) with their username
    for user in message.mentions:
        content = content.replace(f"<@{user.id}>", f"{user.display_name}")
        content = content.replace(f"<@!{user.id}>", f"{user.display_name}")

    # 3️⃣ Replace role mentions (<@&12345>) with their role name
    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")

    # 4️⃣ Replace channel mentions (<#12345>) with their channel name
    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")

    # 5️⃣ Clean up extra spaces
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

    logging.info(f"✅ All messages saved to {MESSAGE_HISTORY_FILE}")


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
