from utilities.constants import GUILD_MEMBER_NAMES


def get_name(message):
    username = message.author.name
    return GUILD_MEMBER_NAMES.get(username, message.author.display_name)
