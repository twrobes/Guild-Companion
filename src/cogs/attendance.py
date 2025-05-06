import logging
from datetime import datetime
import calendar
from typing import Tuple

import discord
import pandas as pd
import asyncpg
from discord import app_commands
from discord.ext import commands

from env import POSTGRESQL_SECRET, ATROCIOUS_ATTENDANCE_CHANNEL_ID

USER_ID_COL = 0
ABSENCE_DATE_COL = 1
START_DATE_COL = 1
END_DATE_COL = 2
DATE_FORMAT = '%Y-%m-%d'
USER_INPUT_DATE_FORMAT = '%m/%d/%Y'


class Attendance(commands.GroupCog, name='attendance'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('Attendance cog loaded.')

    @app_commands.command(
        name='add',
        description='Add a date that you will be absent. Ex: month=4 day=20'
    )
    async def add_absence(self, interaction: discord.Interaction, year: int, month: int, day: int, user: discord.Member = None):
        is_officer = False
        user_id = interaction.user.id

        if user:
            for role in interaction.user.roles:
                if role.name == 'Officer':
                    is_officer = True

            if not is_officer:
                await interaction.response.send_message('You are not allowed to add an absence for another user. Please leave the optional "user" argument blank', ephemeral=True)
                return
            else:
                user_id = user.id

        error_string = Attendance.validate_date(month, day, year)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        standard_date = Attendance.get_standardized_date_string(month, day, year)
        date_obj = datetime.strptime(standard_date, DATE_FORMAT)
        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')

        try:
            get_record_query = """SELECT * FROM attendance WHERE user_id=($1) AND absence_date=($2)"""
            attendance_records = await conn.fetch(get_record_query, user_id, date_obj)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to retrieve data from the database. Please contact Foe for assistance.', ephemeral=True)
            await conn.close()
            return

        if attendance_records:
            await interaction.response.send_message('You already have an absence set for this day.', ephemeral=True)
            await conn.close()
            return

        try:
            insert_absence_query = """INSERT INTO attendance (user_id, absence_date) VALUES ($1, $2)"""
            await conn.execute(insert_absence_query, user_id, date_obj)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to add the absence to the database. Please contact Foe for assistance.', ephemeral=True)
            return
        finally:
            await conn.close()

        year_month_day = (standard_date.split('-')[0], standard_date.split('-')[1], standard_date.split('-')[2])
        await interaction.response.send_message(
            f'Successfully added absence for {(await self.bot.fetch_user(user_id)).display_name} '
            f'on {year_month_day[1]}/{year_month_day[2]}/{year_month_day[0]}', ephemeral=True)

        await Attendance.update_absences_table(self)
        return

    @app_commands.command(
        name='remove',
        description='Remove a date that you previously added as an absence. Ex: month=6 day=9'
    )
    async def remove_absence(self, interaction: discord.Interaction, year: int, month: int, day: int, user: discord.Member = None):
        is_officer = False
        user_id = interaction.user.id

        if user:
            for role in interaction.user.roles:
                if role.name == 'Officer':
                    is_officer = True

            if not is_officer:
                await interaction.response.send_message('You are not allowed to remove an absence for another user. Please leave the optional "user" argument blank',
                                                        ephemeral=True)
                return
            else:
                user_id = user.id

        error_string = Attendance.validate_date(month, day, year)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        standard_date = Attendance.get_standardized_date_string(month, day, year)
        date_obj = datetime.strptime(standard_date, DATE_FORMAT)
        year_month_day = (standard_date.split('-')[0], standard_date.split('-')[1], standard_date.split('-')[2])
        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')

        try:
            get_record_query = """SELECT * FROM attendance WHERE user_id=($1) AND absence_date=($2)"""
            attendance_records = await conn.fetch(get_record_query, user_id, date_obj)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to retrieve data from the database. Please contact Foe for assistance.', ephemeral=True)
            await conn.close()
            return

        if not attendance_records:
            await interaction.response.send_message(
                f'You have not added an absence on {year_month_day[1]}/{year_month_day[2]}/{year_month_day[0]}. Please input a date with an existing absence.', ephemeral=True)
            await conn.close()
            return

        try:
            delete_query = """DELETE FROM attendance WHERE user_id=$1 AND absence_date=$2"""
            await conn.execute(delete_query, user_id, date_obj)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to delete the absence from the database. Please contact Foe for assistance.', ephemeral=True)
            return
        finally:
            await conn.close()

        await interaction.response.send_message(
            f'Successfully removed absence for {(await self.bot.fetch_user(user_id)).display_name} '
            f'on {year_month_day[1]}/{year_month_day[2]}/{year_month_day[0]}', ephemeral=True)

        await Attendance.update_absences_table(self)
        return

    @app_commands.command(
        name='add_vacation',
        description='Add a date range when you will not be attending raid. Ex: start=4/20/2024, end=6/9/2024'
    )
    async def add_vacation(self, interaction: discord.Interaction, start: str, end: str):
        error_string = Attendance.validate_dates_are_chronological(start, end)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        error_string = Attendance.validate_date_input(start)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        error_string = Attendance.validate_date_input(end)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        start_date = datetime.strptime(start, USER_INPUT_DATE_FORMAT)
        end_date = datetime.strptime(end, USER_INPUT_DATE_FORMAT)

        start_error_string = Attendance.validate_date(start_date.month, start_date.day, start_date.year)
        end_error_string = Attendance.validate_date(end_date.month, end_date.day, end_date.year)

        if start_error_string and end_error_string:
            await interaction.response.send_message(
                f'start and end both are invalid dates: '
                f'start - {start_error_string}, end - {end_error_string}', ephemeral=True)
            return
        if start_error_string:
            await interaction.response.send_message(f'start is an invalid date: {start_error_string}', ephemeral=True)
            return
        if end_error_string:
            await interaction.response.send_message(f'end is an invalid date: {end_error_string}', ephemeral=True)
            return

        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')

        try:
            vacation_records = await conn.fetch("""SELECT * FROM vacation WHERE user_id=$1""", interaction.user.id)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to retrieve data from the database. Please contact Foe for assistance.', ephemeral=True)
            await conn.close()
            return

        for record in vacation_records:
            record_start_date = datetime(record[START_DATE_COL].year, record[START_DATE_COL].month, record[START_DATE_COL].day)
            record_end_date = datetime(record[END_DATE_COL].year, record[END_DATE_COL].month, record[END_DATE_COL].day)

            if record_start_date == start_date and record_end_date == end_date:
                await interaction.response.send_message('You have already set a vacation for this date range.', ephemeral=True)
                return

            if record_start_date <= start_date <= record_end_date:
                await interaction.response.send_message('Your start date cannot be within the range of an existing vacation.', ephemeral=True)
                return

            if record_start_date <= end_date <= record_end_date:
                await interaction.response.send_message('Your end date cannot be within the range of an existing vacation.', ephemeral=True)
                return

            if (start_date <= record_start_date <= end_date) or (start_date <= record_end_date <= end_date):
                await interaction.response.send_message('You cannot create a vacation range that intersects an existing vacation.', ephemeral=True)
                return

        try:
            insert_absence_query = """INSERT INTO vacation (user_id, start_date, end_date) VALUES ($1, $2, $3)"""
            await conn.execute(insert_absence_query, interaction.user.id, start_date, end_date)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to add the vacation to the database. Please contact Foe for assistance.', ephemeral=True)
            return
        finally:
            await conn.close()

        await interaction.response.send_message(
            f'Successfully added vacation for {interaction.user.display_name} '
            f'from {start_date.month}/{start_date.day}/{start_date.year} '
            f'to {end_date.month}/{end_date.day}/{end_date.year}.', ephemeral=True)

        await Attendance.update_absences_table(self)
        return

    @app_commands.command(
        name='remove_vacation',
        description='Remove a date range when you will not be attending raid (ex: start=1/3/2024, end=3/7/2024)'
    )
    async def remove_vacation(self, interaction: discord.Interaction, start: str, end: str):
        error_string = Attendance.validate_dates_are_chronological(start, end)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        error_string = Attendance.validate_date_input(start)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        error_string = Attendance.validate_date_input(end)

        if error_string:
            await interaction.response.send_message(error_string, ephemeral=True)
            return

        start_date = datetime.strptime(start, USER_INPUT_DATE_FORMAT)
        end_date = datetime.strptime(end, USER_INPUT_DATE_FORMAT)

        start_error_string = Attendance.validate_date(start_date.month, start_date.day, start_date.year)
        end_error_string = Attendance.validate_date(end_date.month, end_date.day, end_date.year)

        if start_error_string and end_error_string:
            await interaction.response.send_message(f'start and end both are invalid dates: start - {start_error_string}, end - {end_error_string}', ephemeral=True)
            return
        if start_error_string:
            await interaction.response.send_message(f'start is an invalid date: {start_error_string}', ephemeral=True)
            return
        if end_error_string:
            await interaction.response.send_message(f'end is an invalid date: {end_error_string}', ephemeral=True)
            return

        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')

        try:
            get_record_query = """SELECT * FROM vacation WHERE user_id=$1 AND start_date=$2 and end_date=$3"""
            attendance_records = await conn.fetch(get_record_query, interaction.user.id, start_date, end_date)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to retrieve data from the database. Please contact Foe for assistance.', ephemeral=True)
            await conn.close()
            return

        if not attendance_records:
            await interaction.response.send_message(
                f'You have not added a vacation from {start_date.month}/{start_date.day}/{start_date.year} to '
                f'{end_date.month}/{end_date.day}/{end_date.year}.'
                f'Please input a date with an existing absence.', ephemeral=True)
            await conn.close()
            return

        try:
            delete_query = """DELETE FROM vacation WHERE user_id=$1 AND start_date=$2 AND end_date=$3"""
            await conn.execute(delete_query, interaction.user.id, start_date, end_date)
        except (Exception, asyncpg.PostgresError) as e:
            logging.error(e)
            await interaction.response.send_message('Something went wrong while trying to delete the vacation from the database. Please contact Foe for assistance.',
                                                    ephemeral=True)
            return
        finally:
            await conn.close()

        await interaction.response.send_message(
            f'Successfully removed vacation for {interaction.user.display_name} '
            f'from {start_date.month}/{start_date.day}/{start_date.year} '
            f'to {end_date.month}/{end_date.day}/{end_date.year}.', ephemeral=True)

        await Attendance.update_absences_table(self)
        return

    @staticmethod
    def validate_date_input(date):
        if '/' not in date:
            return 'No "/" found in entered date.'

        date_parts = date.split('/')

        if len(date_parts) != 3:
            return 'You must enter month, day, and year only.'

        try:
            if int(date_parts[0]) < 1 or int(date_parts[0]) > 12:
                return 'You must enter a number between 1 and 12 for the month.'
        except ValueError:
            return 'You must enter a number between 1 and 12 for the month.'

        try:
            if int(date_parts[1]) < 1 or int(date_parts[1]) > 31:
                return 'You must enter a number between 1 and 31 for the day.'
        except ValueError:
            return 'You must enter a number between 1 and 12 for the day.'

        try:
            if int(date_parts[2]) < datetime.now().year or int(date_parts[2]) > datetime.now().year + 1:
                return f'You must enter a number between {datetime.now().year} and {datetime.now().year + 1} for the year.'
        except ValueError:
            return f'You must enter a number between {datetime.now().year} and {datetime.now().year + 1} for the year.'

        return ''

    @staticmethod
    def validate_dates_are_chronological(start_date, end_date):
        start_date_obj = datetime(int(start_date.split('/')[2]), int(start_date.split('/')[0]), int(start_date.split('/')[1]))
        end_date_obj = datetime(int(end_date.split('/')[2]), int(end_date.split('/')[0]), int(end_date.split('/')[1]))

        if start_date_obj == end_date_obj:
            return 'You must enter two different dates for the start date and the end date.'

        if start_date_obj > end_date_obj:
            return 'The start date must occur before the end date.'

    @staticmethod
    def validate_date(month: int, day: int, year):
        if year < datetime.now().year:
            return f'{year} occurred in the past. Please input a current or future date.'
        elif year > datetime.now().year + 1:
            return f'{year} is too far in the future, please input {datetime.now().year} or {datetime.now().year + 1}.'

        if month < 1 or month > 12:
            return 'Month must be between 1-12.'
        elif year == datetime.now().year and month < datetime.now().month:
            return f'{month}/{day}/{year} occurred in the past. Please input a current or future date.'

        if day < 1 or day > 31:
            return 'Day must be between 1-31'
        elif datetime.now().month == 2 and (year % 4 == 0) and day > 29:
            return f'Day must not exceed 29 for February. {year} is a leap year.'
        elif datetime.now().month == 2 and (year % 4 > 0) and day > 28:
            return f'Day must not exceed 28 for February. {year} is not a leap year.'
        elif year == datetime.now().year and month == datetime.now().month and day < datetime.now().day:
            return f'{month}/{day}/{year} occurred in the past. Please input a current or future date.'

        match month:
            case 4 | 6 | 9 | 11:
                if day > 30:
                    month_name = calendar.month_name[month]
                    return f'Day must not exceed 30 for {month_name}.'

        return ''

    @staticmethod
    def get_standardized_date_string(month: int, day: int, year: int):
        if day < 10:
            day_str = f'0{day}'
        else:
            day_str = f'{day}'

        if month < 10:
            month_str = f'0{month}'
        else:
            month_str = f'{month}'

        year_str = f'{year}'

        return f'{year_str}-{month_str}-{day_str}'

    async def update_absences_table(self):
        conn = await asyncpg.connect(f'postgres://avnadmin:{POSTGRESQL_SECRET}@atrocious-bot-db-atrocious-bot.l.aivencloud.com:12047/defaultdb?sslmode=require')

        try:
            attendance_records = await conn.fetch("""SELECT * FROM attendance ORDER BY absence_date ASC""")
            vacation_records = await conn.fetch("""SELECT * FROM vacation ORDER BY start_date ASC""")
        except (Exception, asyncpg.PostgresError):
            logging.error("Could not fetch all records from the attendance table and/or vacations table")
            return
        finally:
            await conn.close()

        if not attendance_records:
            logging.info('There are no absences, so not updating the message')

        attendance_channel = self.bot.get_channel(ATROCIOUS_ATTENDANCE_CHANNEL_ID)
        sticky_msg = discord.Embed(
            color=discord.Color.dark_embed(),
            title='Absences'
        )
        is_empty, attendance_dates_dict, vacation_dates_list = await Attendance.get_user_date_list(
            self, attendance_records, vacation_records
        )

        if is_empty:
            sticky_msg.add_field(name='*There are no upcoming absences*', value='')
            await Attendance.delete_bot_messages(self, attendance_channel)
            await attendance_channel.send(embed=sticky_msg)
            return

        table_data = Attendance.get_absence_dict(attendance_dates_dict, vacation_dates_list)
        df = pd.DataFrame(data=table_data)
        df.set_index('', inplace=True)
        df.index.name = None

        await Attendance.delete_bot_messages(self, attendance_channel)
        await attendance_channel.send(f'```{df}```')

        return

    @staticmethod
    def get_absence_dict(absence_dict, vacation_list):
        table_dict = {
            '': [],
            'Name': [],
            'Day': [],
            'Date': []
        }

        longest_name = 0
        longest_date = 0
        longest_month = 0
        longest_day = 3

        for month, absences_list in absence_dict.items():
            if len(absences_list) == 0:
                continue

            month_is_added = False

            for absence in absences_list:
                if longest_name < len(absence['Name']):
                    longest_name = len(absence['Name'])

                if longest_date < len(absence['Date']):
                    longest_date = len(absence['Date'])

                if longest_day < len(absence['Day']):
                    longest_day = len(absence['Day'])

                if not month_is_added:
                    # Add month header
                    table_dict[''].append(month)
                    table_dict['Name'].append('')
                    table_dict['Day'].append('')
                    table_dict['Date'].append('')

                    table_dict[''].append('')
                    table_dict['Name'].append(absence['Name'])
                    table_dict['Day'].append(absence['Day'])
                    table_dict['Date'].append(absence['Date'])

                    if longest_month < len(month):
                        longest_month = len(month)

                    month_is_added = True
                else:
                    table_dict[''].append('')
                    table_dict['Name'].append(absence['Name'])
                    table_dict['Day'].append(absence['Day'])
                    table_dict['Date'].append(absence['Date'])

        if not len(vacation_list) > 0:
            # Add row to separate headers and data
            table_dict[''].insert(0, '-' * longest_month)
            table_dict['Name'].insert(0, '-' * longest_name)
            table_dict['Day'].insert(0, '-' * longest_day)
            table_dict['Date'].insert(0, '-' * longest_date)
        else:
            longest_month = 9

            for vacation in vacation_list:
                if longest_name < len(vacation['Name']):
                    longest_name = len(vacation['Name'])

                if longest_day < len(vacation['Day']):
                    longest_day = len(vacation['Day'])

                if longest_date < len(vacation['Date']):
                    longest_date = len(vacation['Date'])

            # Add row to separate headers and data
            table_dict[''].insert(0, '-' * longest_month)
            table_dict['Name'].insert(0, '-' * longest_name)
            table_dict['Day'].insert(0, '-' * longest_day)
            table_dict['Date'].insert(0, '-' * longest_date)

            # Add a row between absences and vacations
            table_dict[''].append('-' * longest_month)
            table_dict['Name'].append('-' * longest_name)
            table_dict['Day'].append('-' * longest_day)
            table_dict['Date'].append('-' * longest_date)

            # Add vacation header
            table_dict[''].append('Vacations')
            table_dict['Name'].append('')
            table_dict['Day'].append('')
            table_dict['Date'].append('')

            for vacation in vacation_list:
                if len(vacation_list) == 0:
                    break

                table_dict[''].append('')
                table_dict['Name'].append(vacation['Name'])
                table_dict['Day'].append(vacation['Day'])
                table_dict['Date'].append(vacation['Date'])

        return table_dict

    async def get_user_date_list(self, attendance_records: list, vacation_records: list) -> Tuple[bool, dict, list]:
        absence_date_dict = {
            'January': [],
            'February': [],
            'March': [],
            'April': [],
            'May': [],
            'June': [],
            'July': [],
            'August': [],
            'September': [],
            'October': [],
            'November': [],
            'December': [],
        }

        vacation_date_list = []
        attendance_is_empty = False
        guild = self.bot.get_guild(699611111066042409)

        if len(attendance_records) == 0 and len(vacation_records) == 0:
            return True, {}, []

        for user_id, absence_date in attendance_records:
            standard_date = Attendance.get_standardized_date_string(
                absence_date.month, absence_date.day, absence_date.year
            )

            if datetime.strptime(standard_date, DATE_FORMAT) < datetime.now():
                continue

            display_name = (await guild.fetch_member(user_id)).display_name
            absence_date_dict[absence_date.strftime('%B')].append(
                {
                    'Name': display_name,
                    'Day': absence_date.strftime('%a'),
                    'Date': f'{absence_date.month}/{absence_date.day}/{absence_date.year}'
                }
            )

        for user_id, start_date, end_date in vacation_records:
            display_name = (await guild.fetch_member(user_id)).display_name
            vacation_date_list.append(
                {
                    'Name': display_name,
                    'Day': 'N/A',
                    'Date': f'{start_date.month}/{start_date.day}/{start_date.year} - '
                            f'{end_date.month}/{end_date.day}/{end_date.year}'
                }
            )

        return attendance_is_empty, absence_date_dict, vacation_date_list

    async def delete_bot_messages(self, channel):
        messages = [message async for message in channel.history(limit=50)]

        for message in messages:
            if message.author.id == self.bot.user.id:
                await message.delete()

    @staticmethod
    def get_day_suffix(day: int):
        st = [1, 21, 31]
        nd = [2, 22]
        rd = [3, 23]

        if day in st:
            return 'st'
        elif day in nd:
            return 'nd'
        elif day in rd:
            return 'rd'
        else:
            return 'th'


async def setup(bot):
    await bot.add_cog(Attendance(bot), guilds=[
        discord.Object(id=238145730982838272),
        discord.Object(id=699611111066042409)
    ])
