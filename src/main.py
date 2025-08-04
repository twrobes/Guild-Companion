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
VALID_MOONKIN_WORDS = ['kick', 'fuck', 'stair', '400', 'buff', 'nerf', 'meta']

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
    msg_lower = message.content.lower()

    if message.author == bot.user:
        return

    message_reaction_triggered = False

    if 'o7' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send('o7')

    if 'bruh' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send(file=discord.File('resources/bruh.gif'))

    if 'bounce on it' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send('https://i.imgur.com/LtBC4hH.gif')

    if ('kona' in msg_lower or any(user.id == 123499257373261826 for user in message.mentions)) and 'grip' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send("https://cdn.discordapp.com/attachments/1050059557877063681/1382838661661331596"
                                   "/konagrip.gif?ex=684c9c5c&is=684b4adc&hm=42669944c06a6b97bf64c55efd603915a35f70ac044f93e6c1e1fcc828803914&")

    if any(word in msg_lower for word in VALID_MOONKIN_WORDS) and ('moonkin' in msg_lower or 'boomkin' in msg_lower):
        message_reaction_triggered = True
        await message.channel.send(file=discord.File('resources/kick_moonkin_down_stairs.png'))

    if bot.user in message.mentions and not message_reaction_triggered:
        if 'hi' in msg_lower or 'hello' in msg_lower or 'hey' in msg_lower:
            await message.channel.send('<a:hiii:1325574390431223839>')
        elif 'meowdy' in msg_lower:
            await message.channel.send('<a:meowdy:1325576796497772616>')
        elif 'kick' in msg_lower and 'moonkin' in msg_lower or 'boomkin' in msg_lower:
            await message.channel.send(file=discord.File('resources/kick_moonkin_down_stairs.png'))
        else:
            await message.channel.send('<:stare:1270932409428344893>')

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
    corrected_cst_datetime = datetime.datetime.now() - datetime.timedelta(hours=5)

    # Deletes old records from attendance table
    try:
        delete_record_query = """DELETE FROM attendance WHERE absence_date < ($1)"""
        await conn.execute(delete_record_query, corrected_cst_datetime)
        logging.info('Removed past absence records successfully')
    except (Exception, asyncpg.PostgresError) as e:
        logging.error(e)
        await conn.close()

    # Deletes old records from vacation table
    try:
        delete_record_query = """DELETE FROM vacation WHERE end_date < ($1)"""
        await conn.execute(delete_record_query, corrected_cst_datetime)
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
