import discord
from openai import AsyncOpenAI

from env import CHAT_GPT_API_KEY

client = AsyncOpenAI(
    api_key=CHAT_GPT_API_KEY
)


async def get_chat_gpt_response(prompt: discord.Message, bot: discord.Client):
    clean_prompt = clean_message_content(prompt, bot)

    response = await client.responses.create(
        model="gpt-5-nano",
        input=clean_prompt,
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
        content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
        content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")

    # 3️⃣ Replace role mentions (<@&12345>) with their role name
    for role in message.role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")

    # 4️⃣ Replace channel mentions (<#12345>) with their channel name
    for channel in message.channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")

    # 5️⃣ Clean up extra spaces
    return content.strip()
