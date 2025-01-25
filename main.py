import configparser
from wom import Client
from discord.ext import tasks
import discord
import asyncio

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])
GROUP_ID = int(config['wiseoldman']['group_id'])
CHECK_INTERVAL = int(config['settings']['check_interval'])  # Check interval in seconds, directly from config

# Initialize Wise Old Man client
wom_client = Client()

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
        print("Starting check_for_rank_changes task.")
        await wom_client.start()  # Ensure WOM client is started before running the task
        check_for_rank_changes.start()
    else:
        print("check_for_rank_changes task is already running.")


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_for_rank_changes():
    try:
        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        # Unwrap the result to access the group details
        if result.is_ok:
            group = result.unwrap()

            # Access the memberships attribute to get group members
            memberships = group.memberships

            for membership in memberships:
                try:
                    # Access the player object in the membership
                    player = membership.player

                    # Fetch the latest snapshot for each member
                    snapshot = await wom_client.players.get_latest_snapshot(player.id)

                    username = player.display_name
                    ehb = snapshot.computed.ehb  # Efficient Hours Bossed

                    # Compare and notify if rank increases
                    if username in previous_ehb and ehb > previous_ehb[username]:
                        await send_rank_up_message(username, ehb)

                    # Update stored EHB values
                    previous_ehb[username] = ehb
                except Exception as e:
                    print(f"Error fetching player data for {player.username}: {e}")
        else:
            print(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        print(f"Error occurred during rank check: {e}")




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