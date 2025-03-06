import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


class Warcraftlogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('Warcraftlogs cog loaded.')

    @app_commands.command(
        name='rank',
        description='Shows the rank of the guild in the current raid tier'
    )
    async def rank(self, interaction: discord.Interaction):
        url = 'https://raider.io/api/v1/guilds/profile'
        params = {
            'region': 'us',
            'realm': 'Area 52',
            'name': 'Atrocious',
            'fields': 'raid_rankings'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                rank_json = await response.json()

        if response.ok and rank_json is not None:
            await interaction.response.send_message(
                f'__Liberation of Undermine Heroic__\n'
                f'```World  - {rank_json["raid_rankings"]["liberation-of-undermine"]["heroic"]["world"]}\n'
                f'Region - {rank_json["raid_rankings"]["liberation-of-undermine"]["heroic"]["region"]}\n'
                f'Realm  - {rank_json["raid_rankings"]["liberation-of-undermine"]["heroic"]["realm"]}```\n'
                '\n'
                f'__Liberation of Undermine Mythic__\n'
                f'```World  - {rank_json["raid_rankings"]["liberation-of-undermine"]["mythic"]["world"]}\n'
                f'Region - {rank_json["raid_rankings"]["liberation-of-undermine"]["mythic"]["region"]}\n'
                f'Realm  - {rank_json["raid_rankings"]["liberation-of-undermine"]["mythic"]["realm"]}```\n'
            )
        else:
            if rank_json is None:
                logging.error('Error occurred when retrieving rank data: rank_json was None')
            else:
                logging.error(f'Error occurred when retrieving rank data: response was not ok: {response.status}')
            await interaction.response.send_message('An error has occurred. Please DM Foe a screenshot of the command and this response.')


async def setup(bot):
    await bot.add_cog(Warcraftlogs(bot), guilds=[
        discord.Object(id=238145730982838272),
        discord.Object(id=699611111066042409)
    ])
