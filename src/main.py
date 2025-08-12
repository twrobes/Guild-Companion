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
        await message.channel.send("https://cdn.discordapp.com/attachments/347861672137981954/1402066373391417424/bruh.gif?ex=68928f90&is=68913e10&hm="
                                   "64f169e353c4f3493a92a07d3f1810ab5f3d65bd028561fd453e3398f23c615b&")

    if 'bounce on it' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send('https://i.imgur.com/LtBC4hH.gif')

    if ('kona' in msg_lower or any(user.id == 123499257373261826 for user in message.mentions)) and 'grip' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send("https://cdn.discordapp.com/attachments/1050059557877063681/1382838661661331596"
                                   "/konagrip.gif?ex=684c9c5c&is=684b4adc&hm=42669944c06a6b97bf64c55efd603915a35f70ac044f93e6c1e1fcc828803914&")

    if 'gingi' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send("https://media.discordapp.net/attachments/360571569791303681/989015957445943307/ezgif.com-gif-maker_4.gif?ex=689229a3&is=6890d823&hm="
                                   "e89f14000d43fc29ae5c953a2eb1e826955fc1209410bc9c63ec07d84c0cde4c&")

    if 'hopeful' in msg_lower:
        message_reaction_triggered = True
        await message.channel.send("https://cdn.discordapp.com/attachments/347861672137981954/1402083668356497491/hopeful_satisfied.gif?ex=68929fab&is="
                                   "68914e2b&hm=9804f8bba0351bcb6087c08510c7f3084afb0d66bcf74642bfd9fccfd79bf4d2&")

    if any(word in msg_lower for word in VALID_MOONKIN_WORDS) and ('moonkin' in msg_lower or 'boomkin' in msg_lower):
        message_reaction_triggered = True
        await message.channel.send("https://cdn.discordapp.com/attachments/347861672137981954/1402083208027308122/kick_moonkin_down_stairs.png?ex="
                                   "68929f3e&is=68914dbe&hm=ebe0785687680428b94a9511562844cafa39d78bb4cf1a0b333d0d6d897f01d2&")

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
    server_status = await get_area_52_server_status_via_api()
    guild = bot.get_guild(ATROCIOUS_SERVER_ID)
    channel_to_msg = bot.get_channel(ATROCIOUS_GENERAL_CHANNEL_ID)

    conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')
    time_tracking = False

    try:
        get_record_query = """SELECT * FROM time_tracking WHERE id=1"""
        time_tracking = await conn.fetchrow(get_record_query)
    except (Exception, asyncpg.PostgresError) as e:
        logging.error('An error occurred when getting the time tracking record from the db', e)
        await conn.close()

    if server_status:
        if time_tracking and time_tracking["server_maintenance_started"]:
            try:
                await conn.execute("""
                        UPDATE time_tracking
                        SET server_maintenance_started = FALSE
                        WHERE id=1
                    """)
            except (Exception, asyncpg.PostgresError) as e:
                logging.error('An exception occurred when trying to update the server_maintenance_started column to FALSE', e)

        status_msg = 'Area-52 is online'
    else:
        if time_tracking and not time_tracking["server_maintenance_started"]:
            try:
                await conn.execute("""
                        UPDATE time_tracking
                        SET 
                            server_maintenance_started = TRUE,
                            server_maintenance_start_time = $1
                        WHERE id=1
                    """, datetime.datetime.now())
            except (Exception, asyncpg.PostgresError) as e:
                logging.error('An exception occurred when trying to update the server_maintenance_started column to TRUE')

        start_time = time_tracking['server_maintenance_started']
        current_time = datetime.datetime.now()
        seconds_diff = int((current_time - start_time).total_seconds())
        minutes_diff = seconds_diff // 60

        if minutes_diff != 0 and minutes_diff % 30 == 0:
            await channel_to_msg.send(f'Servers have been offline for {minutes_diff/60} hours')

        status_msg = 'Area-52 is offline'

    if guild.me.activity is None:
        activity = discord.CustomActivity(name=status_msg)
        await bot.change_presence(activity=activity)
    elif status_msg != guild.me.activity.name:
        activity = discord.CustomActivity(name=status_msg)
        await bot.change_presence(activity=activity)

        trimmed_status_msg = status_msg.split(' ')[2]
        await channel_to_msg.send(
            f'Area-52 is now {trimmed_status_msg}.'
        )

    await conn.close()


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
