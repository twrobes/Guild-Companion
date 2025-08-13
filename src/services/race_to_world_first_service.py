import asyncio
import logging
import time

import aiohttp
import asyncpg
import discord

from env import POSTGRESQL_SECRET

BACKUP_THUMBNAIL_URL = 'https://wowvendor.com/app/uploads/2025/06/WoW-Manaforge-Omega-raid-guide.jpg'
BOSS_SLUG_LIST = [
    'plexus-sentinel',
    'loomithar',
    'soulbinder-naazindhri',
    'forgeweaver-araz',
    'the-soul-hunters',
    'fractillus',
    'nexus-king-salhadaar',
    'dimensius'
]
# These are in the same order is BOSS_SLUG_LIST
BOSS_URL_LIST = [
    'https://gamingcy.com/wp-content/uploads/2025/06/Plexus-Sentinel.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Loomithar.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Soulbinder-Naazindhri.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Forgeweaver-Araz.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/The-Soul-Hunters.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Fractillus.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Nexus-King-Salhadaar.jpg',
    'https://gamingcy.com/wp-content/uploads/2025/06/Dimensius.jpg'
]
CURRENT_RAID_SLUG = 'manaforge-omega'
DEFAULT_GUILD_IMAGE_URL = 'https://cdn.mos.cms.futurecdn.net/ca871592becab3977c455f6daf5cd1ca.png'
DIFFICULTY_LIST = ['mythic', 'heroic']
KILL_LIMIT = 10


async def retrieve_race_update(rwf_channel):
    update_dict = None

    for difficulty in DIFFICULTY_LIST:
        for boss_idx in range(len(BOSS_SLUG_LIST)):
            # This conditional forces tracking of only the last two heroic bosses
            if boss_idx <= len(BOSS_SLUG_LIST) - 3 and difficulty == 'heroic':
                continue

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
                    update_embed.set_thumbnail(url=BACKUP_THUMBNAIL_URL)
                    logging.warning(f"Something went wrong with the guild image url: {update_dict['guild_image_url']}")

                await rwf_channel.send(embed=update_embed)

                try:
                    if difficulty == 'mythic' and update_dict["boss_name"] == "Dimensius" and update_dict["rank"] == 1:
                        await rwf_channel.send(f'# **{update_dict["guild"]} HAS CLAIMED WORLD FIRST **\n@everyone')
                except Exception:
                    logging.error('An exception occurred sending the world first kill message')


async def get_update_dict(boss_slug: str, boss_rankings_json: dict, difficulty: str):
    boss = difficulty + '-' + boss_slug

    try:
        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')
        get_record_query = """SELECT kills FROM rwf_tracker WHERE boss=($1) AND kills<=($2)"""
        result = await conn.fetch(get_record_query, boss, KILL_LIMIT)
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
        # TODO: Remove this
        logging.info(f'Boss Rankings JSON: \n{boss_rankings_json}')

        target_rank = boss_rankings_json[boss_kills - 1]
        logging.info(f'Target Rank JSON: \n{boss_rankings_json}')
    except IndexError:
        logging.info('Tried to get an invalid index from boss_rankings_json')
        return None

    try:
        guild_image_url = target_rank['guild']['logo']
    except KeyError:
        guild_image_url = DEFAULT_GUILD_IMAGE_URL

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
