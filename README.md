# Guild Companion
Discord Bot built in python to assist the Mythic raiding guild Atrocious on Area-52 in World of Warcraft.

## Getting Started
- Create a discord.log file in atrocious-bot/src/ for local development.
  - Never commit this file.
 
## Current Features
- Server Status Tracking
  - The bot displays as their status if your realm is online or offline, and will send a message to a specified discord channel if the status changes.
- Race to World First Tracker
  - This feature can be turned on and off. When turned on, it will track the top 5 kills of each boss in the new raid. It sends a message if a guild got a top 5 kill in the world of any boss within the raid.
- Admin
  - Send a message to any channel, authored by the bot.
  - Turn on/off the Race to World First Tracker.
- Attendance
  - Add an absence of a specific date.
  - Remove an absence of a specific date.
  - Add a vacation of a specified date range.
  - Remove a vacation of a specified date range.
- Raider.io integration
  - Get your guild's raider.io page link.
  - Show an image of your guild's current progression of a boss within the current raid tier.
- WarcraftLogs integration
  - Display your guild's current rank within the current raid tier.
    - World rank
    - Regional rank
    - Realm rank
- Wowaudit integration
  - Update your character's gear wishlist by providing your character name and a valid Raidbots simulation link.
  - Retreive a list of valid character names that are members of your Wowaudit group.
- Games
  - Gambling
    - The famous gold gambling game that most guilds play during raid breaks, but now in your discord server! Set an amount of gold and how long you want the lobby open. People can freely join or leave during that time. Once the game starts, everyone rolls that number and whoever has the highest roll wins an amount of gold that is the difference between the highest roll and the lowest roll. The person with the lowest roll trades that gold to the highest roller.
  - Deathroll
    - The is a famous MMORPG chat game where one player challenges another player to a deathroll. The player who initiates the contest sets the starting roll value. Each player rolls in turn, and the rolled number is the next number to be rolled by the other player. This continues until one player rolls "1" and that player that rolled the "1" loses, and must trade gold in the amount of the intial roll to the other player.
