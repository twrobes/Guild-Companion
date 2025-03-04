import asyncio
import datetime
import logging
import os

import discord
import asyncpg

from discord.ext import commands, tasks

from cogs.attendance import Attendance
from env import BOT_TOKEN, POSTGRESQL_SECRET, ATROCIOUS_ATTENDANCE_CHANNEL_ID, ATROCIOUS_GENERAL_CHANNEL_ID
from services.wow_server_status_service import get_area_52_server_status_via_api, get_area_52_server_status_via_webpage

ATROCIOUS_SERVER_ID = 699611111066042409
DATE_FORMAT = '%Y-%m-%d'

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord.utils.setup_logging(handler=handler, level=logging.DEBUG)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, application_id='1228562180409131009')


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    check_and_update_bot_attendance_msg.start()
    remove_past_absences.start()
    update_bot_status.start()


async def load():
    for file in os.listdir('./cogs'):
        if file.endswith('.py'):
            await bot.load_extension(f'cogs.{file[:-3]}')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if 'o7' in message.content.lower():
        await message.channel.send('o7')

    if 'bruh' in message.content.lower():
        await message.channel.send('bruh')

    if bot.user in message.mentions:
        if 'hi' in message.content.lower() or 'hello' in message.content.lower() or 'hey' in message.content.lower():
            await message.channel.send('<a:hiii:1325574390431223839>')
        elif 'meowdy' in message.content.lower():
            await message.channel.send('<a:meowdy:1325576796497772616>')
        else:
            await message.channel.send('<:stare:1270932409428344893>')

    if 'scorpion' in message.content.lower():
        await message.channel.send("Have you heard of the hit T.V. series that aired in 2014 called Scorpion? It was a hit Workplace Drama starring Elyes Gabel,"
                                   " Katherine McPhee, and Eddie Kaye Thomas.\nhttps://www.imdb.com/title/tt3514324/")

    await bot.process_commands(message)


@tasks.loop(minutes=1)
async def update_bot_status():
    # await get_area_52_server_status_via_webpage()
    server_status = await get_area_52_server_status_via_api()
    guild = bot.get_guild(ATROCIOUS_SERVER_ID)

    channel_to_msg = bot.get_channel(ATROCIOUS_GENERAL_CHANNEL_ID)
    # TODO: Bring back for opt-in roles
    # raider_role_id = 699622512174301266
    # trial_role_id = 699667525964660826

    if server_status:
        status_msg = 'Area-52 is online'
    else:
        status_msg = 'Area-52 is offline'

    # TODO: Look into this when the server is offline
    # is_online = await get_area_52_server_status_via_webpage()
    #
    # if is_online != 0:
    #     if is_online:
    #         status_msg = 'Area-52 is online'
    #     else:
    #         status_msg = 'Area-52 is offline'

    if guild.me.activity is None:
        activity = discord.CustomActivity(name=status_msg)
        await bot.change_presence(activity=activity)
    elif status_msg != guild.me.activity.name:
        activity = discord.CustomActivity(name=status_msg)
        await bot.change_presence(activity=activity)

        # TODO: Create opt-in roles
        # trimmed_status_msg = status_msg.split(' ')[2]
        # await channel_to_ping.send(
        #     f'<@&{raider_role_id}><@&{trial_role_id}> Area-52 is now {trimmed_status_msg}.'
        # )

        trimmed_status_msg = status_msg.split(' ')[2]
        await channel_to_msg.send(
            f'Area-52 is now {trimmed_status_msg}.'
        )


@tasks.loop(minutes=60)
async def check_and_update_bot_attendance_msg():
    attendance_channel = bot.get_channel(ATROCIOUS_ATTENDANCE_CHANNEL_ID)
    messages = [message async for message in attendance_channel.history(limit=1)]
    message = messages[0]

    if message.author.id != bot.user.id:
        attendance = Attendance(bot)
        await attendance.update_absences_table()


@tasks.loop(hours=24)
async def remove_past_absences():
    conn = await asyncpg.connect(
        f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require'
    )
    current_date = datetime.datetime.now()

    # Deletes old records from attendance table
    try:
        delete_record_query = """DELETE FROM attendance WHERE absence_date < ($1)"""
        await conn.execute(delete_record_query, current_date)
        logging.info('Removed past absence records successfully')
    except (Exception, asyncpg.PostgresError) as e:
        logging.error(e)
        await conn.close()

    # Deletes old records from vacation table
    try:
        delete_record_query = """DELETE FROM vacation WHERE end_date < ($1)"""
        await conn.execute(delete_record_query, current_date)
        logging.info('Removed past absence records successfully')
    except (Exception, asyncpg.PostgresError) as e:
        logging.error(e)
        await conn.close()


async def main():
    # DB Connection
    conn = await asyncpg.connect(
        f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require'
    )

    query_sql = 'SELECT VERSION()'
    version = await conn.fetch(query_sql)
    print(version[0]['version'])

    await load()
    await bot.start(BOT_TOKEN)


asyncio.run(main())
