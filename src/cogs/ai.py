import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

from env import CHAT_GPT_API_KEY
from services.chat_gpt_service import get_channel_history_by_days

client = AsyncOpenAI(
    api_key=CHAT_GPT_API_KEY
)


class AI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('AI cog loaded.')

    @app_commands.command(
        name='summarize_chat',
        description='Summarize convo in this channel.\n'
                    'Example: 1 day 30 hours would summarize the last 54 hours.'
    )
    @app_commands.describe(
        hours="Include messages from this many hours in the past.",
        days="Optional: Include messages from this many days in the past."
    )
    async def summarize_chat(self, interaction: discord.Interaction, hours: int, days: int = 0):
        await interaction.response.defer()

        system_prompt = """
            You are an assistant to a Mythic Raiding guild in World of Warcraft that summarizes Discord channel conversations.
            Provide a clear, accurate summary of what happened in under 750 words.
            Utilize markdown as needed since Discord messages support markdown.
            Do not alter user names; use them exactly as shown in the chat log.
            """

        user_prompt = f"""
            Below is a chronological log of messages from a Discord channel.
            Summarize the conversation clearly and concisely.

            === BEGIN CHAT LOG ===
            {await get_channel_history_by_days(interaction, days, hours)}
            === END CHAT LOG ===
            """

        response = await client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

        await interaction.followup.send(response.choices[0].message.content.strip()[:1800])


async def setup(bot):
    await bot.add_cog(AI(bot), guilds=[
        discord.Object(id=238145730982838272),
        discord.Object(id=699611111066042409)
    ])
