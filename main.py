import configparser
import discord
from discord.ext import tasks
from wom import Client

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])
GROUP_ID = int(config['wiseoldman']['group_id'])
API_KEY = config['wiseoldman'].get('api_key', None)
CHECK_INTERVAL = int(config['settings']['check_interval'])

# Initialize Wise Old Man and Discord clients
wom_client = Client(api_key=API_KEY) if API_KEY else Client()
discord_client = discord.Client()

# Dictionary to store previous EHB values
previous_ehb = {}

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')
    check_for_rank_changes.start()

@tasks.loop(hours=CHECK_INTERVAL)  # Interval from config.ini
async def check_for_rank_changes():
    try:
        group = wom_client.groups.get_group(GROUP_ID)
        members = group.members

        for member in members:
            player = wom_client.players.get_player(member.username)
            ehb = player.ehb

            if member.username in previous_ehb:
                if ehb > previous_ehb[member.username]:
                    await send_rank_up_message(member.username, ehb)

            previous_ehb[member.username] = ehb
    except Exception as e:
        print(f"Error occurred during update: {e}")

async def send_rank_up_message(username, ehb):
    try:
        channel = discord_client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f'🎉 Congratulations {username} on achieving {ehb} EHB! 🎉')
        else:
            print(f"Channel with ID {CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error sending message: {e}")

# Run the Discord bot
discord_client.run(DISCORD_TOKEN)