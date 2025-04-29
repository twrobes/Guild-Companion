import asyncio
import io
import logging
import os

import discord
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from io import BytesIO

RAIDERIO_MYTHIC_PLUS_LEADERBOARD_URL = 'https://raider.io/guilds/us/area-52/Atrocious/roster#mode=mythic_plus'


async def retrieve_mythic_plus_update(mythic_plus_channel):
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
    driver.get(RAIDERIO_MYTHIC_PLUS_LEADERBOARD_URL)
    driver.execute_script("""document.documentElement.style.zoom = '90%';""")

    await asyncio.sleep(6)

    try:
        accept_button = WebDriverWait(driver, 4).until(
            ec.element_to_be_clickable((By.CLASS_NAME, "cookie-footer--accept_button"))
        )
        accept_button.click()
    except Exception as e:
        logging.warning("No cookie banner or unable to click:", e)

    png = driver.get_screenshot_as_png()
    driver.quit()

    # Crop image
    image = Image.open(BytesIO(png))

    if os.name == 'nt':
        left = 10
        top = 685
        right = 766
        bottom = 1174
    else:
        left = 10
        top = 685
        right = 766
        bottom = 1174

    mythic_plus_image = image.crop((left, top, right, bottom))
    buffer = io.BytesIO()
    mythic_plus_image.save(buffer, 'png')
    buffer.seek(0)

    await mythic_plus_channel.send(file=discord.File(fp=buffer, filename='mythic_plus_leaderboard_image.png'))
