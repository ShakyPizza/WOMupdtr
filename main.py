import configparser
import requests
import discord
from discord.ext import tasks

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])  # Ensure channel ID is an integer
GROUP_ID = int(config['wiseoldman']['group_id'])
CHECK_INTERVAL = int(config['settings']['check_interval'])

# API Base URL
BASE_URL = "https://api.wiseoldman.net/v2"

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
discord_client = discord.Client(intents=intents)

# Dictionary to store previous EHB values
previous_ehb = {}

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')
    if not check_for_rank_changes.is_running():
        check_for_rank_changes.start()
    else:
        print("Task already running, skipping start.")


@tasks.loop(hours=CHECK_INTERVAL)  # Interval from config.ini
async def check_for_rank_changes():
    try:
        # Fetch group details
        group_url = f"{BASE_URL}/groups/{GROUP_ID}"
        response = requests.get(group_url)
        response.raise_for_status()
        group_data = response.json()

        # Access the "memberships" field
        memberships = group_data.get("memberships", [])

        for member in memberships:
            player = member.get("player", {})
            username = player.get("displayName", "Unknown")
            ehb = player.get("ehb", 0)

            # Check and compare EHB
            if username in previous_ehb:
                if ehb > previous_ehb[username]:
                    await send_rank_up_message(username, ehb)

            # Update previous EHB
            previous_ehb[username] = ehb
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