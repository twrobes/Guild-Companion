import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.race_to_world_first_service import retrieve_race_update

ADMIN_USER_ID = 104797389373599744
RWF_CHANNEL_ID = 1332825068601868380


class Admin(commands.GroupCog, name='admin'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('Admin cog loaded.')

    @app_commands.command(
        name='server_message',
        description='Sends a message to a specified guild channel'
    )
    async def send_server_message(self, interaction: discord.Interaction, channel_id: str, message: str):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message('You are not allowed to use this command', ephemeral=True)
            return

        channel = self.bot.get_channel(int(channel_id))
        await channel.send(message)
        await interaction.response.send_message('Message sent successfully', ephemeral=True)

    @app_commands.command(
        name='rwf_tracker',
        description='Starts the Race to World First updates tracker'
    )
    async def start_rwf_tracker(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message('You are not allowed to use this command', ephemeral=True)
            return

        match action:
            case 'start':
                self.rwf_tracker.start()
                action_str = 'started'
            case 'stop':
                self.rwf_tracker.stop()
                action_str = 'stopped'
            case _:
                await interaction.response.send_message(f'Invalid input. The two available options are "start" and "stop". You entered: {action}')
                return

        await interaction.response.send_message(f'Race to World First tracker {action_str} successfully.')

    @tasks.loop(seconds=60)
    async def rwf_tracker(self):
        rwf_channel = self.bot.get_channel(RWF_CHANNEL_ID)
        await retrieve_race_update(rwf_channel)


async def setup(bot):
    await bot.add_cog(Admin(bot), guilds=[
        discord.Object(id=238145730982838272),
        # discord.Object(id=699611111066042409)
    ])
