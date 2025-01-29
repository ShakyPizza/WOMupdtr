import configparser
from wom import Client
from discord.ext import tasks
from discord.ext import commands
import discord
from utils.rank_utils import load_ranks, save_ranks
from utils.log_csv import log_ehb_to_csv
from datetime import datetime
from utils.commands import setup_commands
import os


# Load configuration
config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_file)


# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])
GROUP_ID = int(config['wiseoldman']['group_id'])
CHECK_INTERVAL = int(config['settings']['check_interval'])  
RUN_AT_STARTUP = config['settings'].getboolean('run_at_startup', True)  
PRINT_TO_CSV = config['settings'].getboolean('print_to_csv', True)  
PRINT_CSV_CHANGES = config['settings'].getboolean('print_csv_changes', True)  
POST_TO_DISCORD = config['settings'].getboolean('post_to_discord', True)  
GROUP_PASSCODE = config['wiseoldman']['GROUP_PASSCODE'] 


try:
    RUN_AT_STARTUP = config['settings'].getboolean('run_at_startup')
except (ValueError, KeyError):
    RUN_AT_STARTUP = True  # Default to True if the value is missing or invalid
    print("Invalid or missing 'run_at_startup' setting. Defaulting to True.")

# Set up the bot with a command prefix
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
discord_client = commands.Bot(command_prefix="/", intents=intents)  # Use commands.Bot


# Initialize Wise Old Man client
wom_client = Client()


@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')

    # Start the Wise Old Man client session
    await wom_client.start()

    # Call the one-time member and ranks listing function if enabled
    if RUN_AT_STARTUP:
        print("Running list_all_members_and_ranks at startup.")
        await list_all_members_and_ranks()

    # Start rank checking task if not already running
    if not check_for_rank_changes.is_running():
        print("Starting check_for_rank_changes task.")
        check_for_rank_changes.start()
    else:
        print("check_for_rank_changes task is already running.")

def get_rank(ehb, ranks_file=os.path.join(os.path.dirname(__file__), 'ranks.ini')):
    try:
        config = configparser.ConfigParser()
        config.read(ranks_file)

        # Parse ranks from the INI file
        for range_key, rank_name in config['Group Ranking'].items():
            if '+' in range_key:  # Handle ranges like '1500+'
                lower_bound = int(range_key.replace('+', ''))
                if ehb >= lower_bound:
                    return rank_name
            else:
                # Handle ranges like '0-10'
                lower_bound, upper_bound = map(int, range_key.split('-'))
                if lower_bound <= ehb < upper_bound:
                    return rank_name
    except Exception as e:
        print(f"Error reading ranks.ini: {e}")
    return "Unknown"  # Default if no rank matches


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_for_rank_changes():
    try:
        print("Starting player comparison...")
        ranks_data = load_ranks()  # Load the existing ranks data

        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships
            print(f"Fetched group details successfully.", " Next comparison in", CHECK_INTERVAL, "seconds.")
            for membership in memberships:
                try:
                    player = membership.player
                    username = player.display_name
                    ehb = round(player.ehb, 2)  # Rounded to 2 decimals
                    rank = get_rank(ehb)  # Determine rank
                    discord_name = ""

                    # Fetch the last known rank and EHB
                    last_data = ranks_data.get(username, {})
                    last_ehb = last_data.get("last_ehb", 0)
                    last_rank = last_data.get("rank", "Unknown")

                    # Compare and notify if rank increases
                    if ehb > last_ehb:
                        await send_rank_up_message(username, rank, last_rank, ehb)

                    # Update the ranks data
                    ranks_data[username] = {"last_ehb": ehb, "rank": rank, "discord_name": discord_name}
                    if PRINT_TO_CSV:
                        log_ehb_to_csv(username, ehb, discord_name)  # Log EHB to the CSV file

                except Exception as e:
                    print(f"Error processing player data for {player.username}: {e}")

            # Save the updated ranks data
            save_ranks(ranks_data)

        else:
            print(f"Failed to fetch group details: {result.unwrap_err()}")

    except Exception as e:
        print(f"Error occurred during rank check: {e}")

async def list_all_members_and_ranks():
    try:
        # Ensure the Wise Old Man client's HTTP session is started
        await wom_client.start()

        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships
            group_name = group.name

            # Extract players and sort by EHB descending
            players = []
            for membership in memberships:
                try:
                    player = membership.player
                    username = player.display_name
                    ehb = round(player.ehb, 2)  # Rounded to 2 decimals
                    if ehb > 0:  # Exclude members with 0 EHB
                        rank = get_rank(ehb)  # Determine rank from the ranks.ini file
                        players.append((username, rank, ehb))
                except Exception as e:
                    print(f"Error processing player data for {membership.player.username}: {e}")

            # Sort players by EHB descending
            players.sort(key=lambda x: x[2], reverse=True)

            # Prepare the message header
            message_lines = []
            chunk = [f"**{group_name} Ranking on {datetime.now().strftime('%Y-%m-%d %H:%M')}**\n"]
            chunk.append("```")
            chunk.append(f"{'#':<4}{'Player':<20}{'Rank':<15}{'EHB':<10}")
            chunk.append(f"{'-'*50}")

            for index, (username, rank, ehb) in enumerate(players, start=1):
                line = f"{index:<4}{username:<20}{rank:<15}{ehb:<10}"

                # Check if adding this line exceeds Discord's 2000 character limit
                if sum(len(l) + 1 for l in chunk) + len(line) + 5 > 2000:  # +5 accounts for closing block
                    chunk.append("```")
                    message_lines.append("\n".join(chunk))
                    chunk = ["```"]  # Start a new block

                chunk.append(line)

            # Add the final chunk
            if len(chunk) > 1:
                chunk.append("```")
                message_lines.append("\n".join(chunk))

            # Send each chunk as a separate message
            channel = discord_client.get_channel(CHANNEL_ID)
            if channel:
                print(f"Sending message to channel: {channel.name}")
                for message in message_lines:
                    await channel.send(message)
            else:
                print(f"Channel with ID {CHANNEL_ID} not found.")
        else:
            print(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        print(f"Error occurred while listing members and ranks: {e}")


async def send_rank_up_message(username, new_rank, old_rank, ehb):
    try:
        if new_rank != old_rank:  # Only send a message if the rank has changed
            channel = discord_client.get_channel(CHANNEL_ID)
            if channel:
                if POST_TO_DISCORD:
                    await channel.send(f'🎉 Congratulations {username} on moving up to the rank of {new_rank} with {ehb} EHB! 🎉')
                    print(f"Sent rank up message for {username} to channel: {channel.name}")
            else:
                print(f"Channel with ID {CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error sending message: {e}")


# Initialize commands
setup_commands(discord_client, wom_client, GROUP_ID, get_rank, list_all_members_and_ranks, GROUP_PASSCODE)

# Run the Discord bot
discord_client.run(DISCORD_TOKEN)