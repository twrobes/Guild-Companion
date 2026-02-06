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
        description='Summarize the conversation within a chat channel. days - how many days in the past. hours - how many hours in the past. '
                    'E.g. 1 day 24 hours would be the past 48 hours.'
    )
    async def summarize_chat(self, interaction: discord.Interaction, days: int, hours: int):
        await interaction.response.defer()

        system_prompt = """
            You are an assistant to a Mythic Raiding guild in World of Warcraft that summarizes Discord channel conversations.
            Provide a clear, accurate summary of what happened in under 500 words.
            Utilize markdown as needed since Discord messages support markdown.
            """

        user_prompt = f"""
            Below is a chronological log of messages from a Discord channel.
            Summarize the conversation clearly and concisely. Feel free to use names/usernames based on who wrote messages you are referencing in your report.

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
