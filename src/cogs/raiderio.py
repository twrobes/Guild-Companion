import asyncio
import io
import os

import discord
from discord import app_commands
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from io import BytesIO

RAIDERIO_WIDGET_URL = ('https://raider.io/widgets/boss-progress?raid=latest&name_style=logo&difficulty=mythic&region=us&realm=area-52&guild=Atrocious&boss=latest'
                       '&period=until_kill&orientation=rect&hide=&chromargb=transparent&theme=dragonflight')


class Raiderio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('Raiderio cog loaded.')

    @app_commands.command(
        name='raiderio',
        description="Links the guild's raider.io page."
    )
    async def raider_io(self, interaction: discord.Interaction):
        await interaction.response.send_message('https://raider.io/guilds/us/area-52/Atrocious')

    @app_commands.command(
        name='prog',
        description='Shows the progress of the guild for the current raid tier.'
    )
    async def prog(self, interaction: discord.Interaction):
        await interaction.response.defer()
        buffer = await self.get_image_buffer()
        await interaction.followup.send(file=discord.File(fp=buffer, filename='prog_image.png'))

    @staticmethod
    async def get_image_buffer():
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")

        if os.name == 'nt':
            chrome_install = ChromeDriverManager().install()
            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            chrome_service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        else:
            chrome_service = Service(executable_path='/usr/bin/chromedriver', options=chrome_options)
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

        # Gets the image
        driver.get(RAIDERIO_WIDGET_URL)
        await asyncio.sleep(5)
        png = driver.get_screenshot_as_png()
        driver.quit()

        # Crop image
        image = Image.open(BytesIO(png))

        if os.name == 'nt':
            left = 0
            top = 40
            right = 625
            bottom = 390
        else:
            left = 0
            top = 32
            right = 499
            bottom = 312

        prog_image = image.crop((left, top, right, bottom))
        buffer = io.BytesIO()
        prog_image.save(buffer, 'png')
        buffer.seek(0)

        return buffer


async def setup(bot):
    await bot.add_cog(Raiderio(bot), guilds=[
        discord.Object(id=238145730982838272),
        discord.Object(id=699611111066042409)
    ])
