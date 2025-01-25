import configparser
from wom import Client
from discord.ext import tasks
from discord.ext import commands
import discord
import csv
from datetime import datetime


# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])
GROUP_ID = int(config['wiseoldman']['group_id'])
CHECK_INTERVAL = int(config['settings']['check_interval'])  # Check interval in seconds, directly from config
RUN_AT_STARTUP = config['settings'].getboolean('run_at_startup', True)  # Configurable startup setting

try:
    RUN_AT_STARTUP = config['settings'].getboolean('run_at_startup')
except (ValueError, KeyError):
    RUN_AT_STARTUP = True  # Default to True if the value is missing or invalid
    print("Invalid or missing 'run_at_startup' setting. Defaulting to True.")

# Set up the bot with a command prefix
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
discord_client = commands.Bot(command_prefix="/", intents=intents)  # Use commands.Bot

# Initialize Wise Old Man client
wom_client = Client()

# Dictionary to store previous EHB values
previous_ehb = {}


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


def get_rank(ehb, ranks_file='ranks.ini'):
    try:
        config = configparser.ConfigParser()
        config.read(ranks_file)

        # Parse ranks from the INI file
        for range_key, rank_name in config['Rich Boys Ranking'].items():
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


# Command: Refresh Rankings
@discord_client.command(name="refresh")
async def refresh(ctx):
    """Refreshes and posts the updated Rich Boys Rankings."""
    try:
        await list_all_members_and_ranks(ctx)
    except Exception as e:
        await ctx.send(f"❌ Error refreshing rankings: {e}")


# Command: Update a specific user
@discord_client.command(name="update")
async def update(ctx, username: str):
    """Fetches and updates the rank for a specific user."""
    try:
        await wom_client.start()
        result = await wom_client.players.search(username)

        if result.is_ok:
            player = result.unwrap()
            ehb = round(player.ehb, 2)
            rank = get_rank(ehb)
            await ctx.send(f"✅ {player.display_name}: {rank} ({ehb} EHB)")
        else:
            await ctx.send(f"❌ Could not find a player with username '{username}'.")
    except Exception as e:
        await ctx.send(f"❌ Error updating {username}: {e}")


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_for_rank_changes():
    try:
        print("Starting player comparison...")
        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships
              
            for membership in memberships:
                try:
                    player = membership.player

                    username = player.display_name
                    ehb = round(player.ehb, 2)  # Rounded to 2 decimals
                    rank = get_rank(ehb)  # Determine rank
                    
                    # Compare and notify if rank increases
                    if username in previous_ehb and ehb > previous_ehb[username]:
                        await send_rank_up_message(username, f"{rank} ({ehb} EHB)")

                    # Update stored EHB values
                    previous_ehb[username] = ehb
                    log_ehb_to_csv(username, ehb)  # Log EHB to the CSV file

                except Exception as e:
                    print(f"Error processing player data for {player.username}: {e}")
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
            chunk = ["**Rich Boys Ranking**\n"]
            chunk.append("```")
            chunk.append(f"{'#':<4}{'Player':<20}{'Rank':<15}{'EHB':<10}")
            chunk.append(f"{'-'*50}")

            for index, (username, rank, ehb) in enumerate(players, start=1):
                line = f"{index:<4}{username:<20}{rank:<15}{ehb:<10}"

                # Check if adding this line exceeds Discord's 4000 character limit
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


def log_ehb_to_csv(username, ehb, file_name="ehb_log.csv"):
    """Logs the username, EHB value, and timestamp to a CSV file."""
    try:
        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, username, ehb])
            print(f"Logged {username} with {ehb} EHB at {timestamp} to {file_name}.")
    except Exception as e:
        print(f"Error logging to CSV: {e}")


async def send_rank_up_message(username, rank, ehb):
    try:
        channel = discord_client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f'🎉 Congratulations {username} on achieving the rank of {rank} with {ehb} EHB! 🎉')
        else:
            print(f"Channel with ID {CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error sending message: {e}")


# Run the Discord bot
discord_client.run(DISCORD_TOKEN)
