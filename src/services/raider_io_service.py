import asyncio
import datetime
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
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor,SitePerProcess,IsolateOrigins")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-client-side-phishing-detection")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")

    if os.name == 'nt':
        chrome_install = ChromeDriverManager().install()
        folder = os.path.dirname(chrome_install)
        chromedriver_path = os.path.join(folder, "chromedriver.exe")
        chrome_service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    else:
        chrome_service = Service(executable_path='/usr/bin/chromedriver', options=chrome_options)
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    driver.set_page_load_timeout(60)

    # Gets the image
    try:
        driver.get(RAIDERIO_MYTHIC_PLUS_LEADERBOARD_URL)
    except Exception as e:
        logging.error(f'Could not retrieve raider.io mythic plus webpage: {e}')

    await asyncio.sleep(15)
    driver.execute_script("""document.documentElement.style.zoom = '90%';""")

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
        left = 560
        top = 598
        right = 1158
        bottom = 1095
    else:
        left = 445
        top = 482
        right = 935
        bottom = 877

    mythic_plus_image = image.crop((left, top, right, bottom))
    buffer = io.BytesIO()
    mythic_plus_image.save(buffer, 'png')
    buffer.seek(0)

    current_date = datetime.datetime.now().strftime('%m/%d/%Y')
    message = f"# Mythic+ Top 10 Leaderboard - {current_date}"

    await mythic_plus_channel.send(content=message, file=discord.File(fp=buffer, filename='mythic_plus_leaderboard_image.png'))
