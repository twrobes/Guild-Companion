import asyncio
import logging
import time

import aiohttp
import asyncpg
import discord

from env import POSTGRESQL_SECRET

BOSS_SLUG_LIST = [
    'vexie-and-the-geargrinders',
    'cauldron-of-carnage',
    'rik-reverb',
    'stix-bunkjunker',
    'sprocketmonger-lockenstock',
    'onearmed-bandit',
    'mugzee-heads-of-security',
    'chrome-king-gallywix'
]
# These are in the same order is BOSS_SLUG_LIST
BOSS_URL_LIST = [
    'https://i.imgur.com/JXqYlMx.png',
    'https://i.ytimg.com/vi/pswYHwWmINo/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLBPObjthefR6dk2YFy8iv5RtzW3Qg',
    'https://i.imgur.com/yp4M6uk.png',
    'https://i.ytimg.com/vi/GrHCt1dPeTg/maxresdefault.jpg',
    'https://i.ytimg.com/vi/gmWWZIQFw0U/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLDxfpZRtd0W4t0hFjfHhNZMazvk-Q',
    'https://i.ytimg.com/vi/jMGS3Cm-V3U/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLD9CXc3VxVyXS94dZV2L3K_SKKsyg',
    'https://i.imgur.com/ST1mtIs.png',
    'https://i.imgur.com/jSp3TfY.png'
]
CURRENT_RAID_SLUG = 'liberation-of-undermine'
DIFFICULTY_LIST = ['mythic', 'heroic']


async def retrieve_race_update(rwf_channel):
    update_dict = None

    for difficulty in DIFFICULTY_LIST:
        for boss_idx in range(len(BOSS_SLUG_LIST)):
            get_boss_rank_url = f"https://raider.io/api/v1/raiding/boss-rankings?raid={CURRENT_RAID_SLUG}&boss={BOSS_SLUG_LIST[boss_idx]}&difficulty={difficulty}&region=world"

            async with aiohttp.ClientSession() as session:
                async with session.get(get_boss_rank_url) as response:
                    boss_rankings = await response.json()

            if response.ok and boss_rankings is not None and len(boss_rankings) != 0:
                update_dict: dict | None = await get_update_dict(BOSS_SLUG_LIST[boss_idx], boss_rankings['bossRankings'], difficulty)
            elif boss_rankings is None:
                logging.error(f'JSON response was none. JSON content: {boss_rankings}')
            elif 400 <= response.status < 500:
                logging.error(f'Page or content was not found. Status code: {response.status}')
            elif 500 <= response.status < 600:
                logging.error(f'Raider.io is down, their server returned a status: {response.status}')
            else:
                logging.error('An unknown error occurred when requesting the raid statistic')

            await asyncio.sleep(2)

            if update_dict is None:
                continue
            else:
                update_msg = (f'**{update_dict["guild"]}** achieved the world {await get_formatted_number(update_dict["rank"])} kill of {difficulty.title()} '
                              f'{update_dict["boss_name"]}!')
                update_embed = discord.Embed(
                    color=discord.Color.dark_embed(),
                    title='Race to World First'
                )
                update_embed.add_field(name=f'**NEW {difficulty.upper()} KILL**', value=update_msg, inline=False)
                update_embed.add_field(name=f'Time of kill', value=f'<t:{int(time.time())}:F>', inline=False)
                update_embed.add_field(name='', value='', inline=False)
                update_embed.set_image(url=BOSS_URL_LIST[boss_idx])

                try:
                    if update_dict["guild_image_url"] is not None or len(update_dict["guild_image_url"]) != 0:
                        update_embed.set_thumbnail(url=update_dict["guild_image_url"])
                except Exception:
                    update_embed.set_thumbnail(url='https://i.imgur.com/kfgdl4a.png')
                    logging.warning(f"Something went wrong with the guild image url: {update_dict['guild_image_url']}")

                await rwf_channel.send(embed=update_embed)

                try:
                    if ((update_dict["guild"] == 'Liquid' or update_dict["guild"] == 'Echo') and difficulty == 'mythic'
                            and update_dict["boss_name"] == "Chrome King Gallywix" and update_dict["rank"] == 1):
                        await rwf_channel.send(f'# **{update_dict["guild"]} HAS CLAIMED WORLD FIRST **\n@everyone')
                except Exception:
                    logging.error('An exception occurred sending the world first kill message')


async def get_update_dict(boss_slug: str, boss_rankings_json: dict, difficulty):
    boss = difficulty + '-' + boss_slug

    try:
        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')
        get_record_query = """SELECT kills FROM rwf_tracker WHERE boss=($1)"""
        result = await conn.fetch(get_record_query, boss)
        boss_kills = result[0]['kills']
    except (Exception, asyncpg.PostgresError) as e:
        logging.error(f'The database transaction to retrieve {boss_slug} boss record had an error: {e}')
        return None

    if len(boss_rankings_json) == 0:
        return None
    elif len(boss_rankings_json) <= boss_kills:
        return None

    boss_kills += 1

    try:
        update_record_query = f"""UPDATE rwf_tracker SET kills=$1 WHERE boss=$2"""
        await conn.execute(update_record_query, boss_kills, boss)
    except (Exception, asyncpg.PostgresError) as e:
        logging.error(f'The database transaction to update boss kills had an error: {e}')
        return None

    await conn.close()

    try:
        target_rank = boss_rankings_json[boss_kills - 1]
    except IndexError:
        logging.info('Tried to get an invalid index from boss_rankings_json')
        return None

    try:
        guild_image_url = target_rank['guild']['logo']
    except KeyError:
        guild_image_url = None

    if difficulty == 'heroic' and boss_slug != 'chrome-king-gallywix':
        return None

    return {
        "boss_name": boss_slug.replace("-", " ").title(),
        "guild": target_rank['guild']['name'],
        "guild_image_url": guild_image_url,
        "rank": target_rank['rank']
    }


async def get_formatted_number(rank: int) -> str:
    rank_str = str(rank)

    if rank_str == '11':
        return rank_str + 'th'

    if rank_str == '12':
        return rank_str + 'th'

    if rank_str == '13':
        return rank_str + 'th'

    match rank_str[-1]:
        case '1':
            return rank_str + 'st'
        case '2':
            return rank_str + 'nd'
        case '3':
            return rank_str + 'rd'
        case '0' | '4' | '5' | '6' | '7' | '8' | '9':
            return rank_str + 'th'
        case _:
            logging.error(f'Got an invalid value for boss rank: {rank}')
            return 'rank'
