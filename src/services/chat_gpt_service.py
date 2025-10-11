import discord
from openai import AsyncOpenAI

from env import CHAT_GPT_API_KEY

client = AsyncOpenAI(
    api_key=CHAT_GPT_API_KEY
)


async def get_chat_gpt_response(message: discord.Message, bot: discord.Client):
    clean_prompt = clean_message_content(message, bot)
    system_prompt = """
    - By default, give a normal response.
    - **IF THE QUESTIONS IS RELATED TO WORLD OF WARCRAFT**, then you are a World of Warcraft pro mythic raider.
    - Keep responses short to medium in length depending on what makes sense, but under 150 words.
    - If you detect a user is using internet memes or is sarcastic, respond in the same way, with memes and sarcasm as appropriate. Do it tastefully.
    - Make fun of the user if they ask something not allowed or goes against OpenAI guidelines.
    - You are allowed to be negative and act like a gamer when talking about world of warcraft.
    - Do not be so defensive if people are talking negatively about a subject. Play along.
    - Be more conservative when using "!", you don't need to end every sentence with an exclamation point.
    - If someone asks what your origin, who created you, or something similar, choose a random famous character from World of Warcraft
    """

    reply_text = await get_replied_text(message)
    print(reply_text)
    print('hi')

    if reply_text:
        message = f'System Prompt: {system_prompt}\nQuote: {reply_text}\nUser: {clean_prompt}'
    else:
        message = f'System Prompt: {system_prompt}\nUser: {clean_prompt}'

    response = await client.responses.create(
        model="gpt-4.1-nano",
        input=message,
        temperature=1.1,
        top_p=0.8,
        store=False,
    )

    return response.output_text


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

