import functools
import io
import time

import discord
from discord import app_commands
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from io import BytesIO

RAIDERIO_WIDGET_URL = ('https://raider.io/widgets/boss-progress?raid=latest&name_style=logo&difficulty=latest&region=us'
                       '&realm=area-52&guild=Atrocious&boss=latest&period=until_kill&orientation=rect'
                       '&hide=&chromargb=transparent&theme=dragonflight')


class Raiderio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('Raiderio cog loaded.')

    @app_commands.command()
    async def prog(self, interaction: discord.Interaction):
        await interaction.response.defer()

        buffer_partial = functools.partial(self.get_image_buffer)
        buffer = await self.bot.loop.run_in_executor(None, buffer_partial)

        await interaction.followup.send(file=discord.File(fp=buffer, filename='prog_image.png'))

    @staticmethod
    def get_image_buffer():
        chrome_service = Service(ChromeDriverManager().install())
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")

        # Gets the image
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.get(RAIDERIO_WIDGET_URL)
        time.sleep(3)
        png = driver.get_screenshot_as_png()
        driver.quit()

        # Crop image
        image = Image.open(BytesIO(png))
        left = 0
        top = 40
        right = 625
        bottom = 390

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
