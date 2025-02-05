import configparser
import os
from datetime import datetime
from discord.ext import tasks, commands
import discord

from wom import Client
from utils.rank_utils import load_ranks, save_ranks
from utils.log_csv import log_ehb_to_csv
from utils.commands import setup_commands

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

def log(message: str):
    """Logs a message with the current timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")

# ------------------------------------------------------------------------------
# Configuration Loading
# ------------------------------------------------------------------------------

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_file)

# Discord and Wise Old Man settings
DISCORD_TOKEN       = config['discord']['token']
CHANNEL_ID          = int(config['discord']['channel_id'])
GROUP_ID            = int(config['wiseoldman']['group_id'])
GROUP_PASSCODE      = config['wiseoldman']['GROUP_PASSCODE']
CHECK_INTERVAL      = int(config['settings']['check_interval'])
RUN_AT_STARTUP      = config['settings'].getboolean('run_at_startup', True)
PRINT_TO_CSV        = config['settings'].getboolean('print_to_csv', True)
PRINT_CSV_CHANGES   = config['settings'].getboolean('print_csv_changes', True)
POST_TO_DISCORD     = config['settings'].getboolean('post_to_discord', True)
DEBUG               = config['settings'].getboolean('debug', False)

# ------------------------------------------------------------------------------
# Discord Client and Wise Old Man Client Initialization
# ------------------------------------------------------------------------------

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
discord_client = commands.Bot(command_prefix="/", intents=intents)
wom_client = Client()

# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------

def get_rank(ehb, ranks_file=os.path.join(os.path.dirname(__file__), 'ranks.ini')):
    """
    Determines the rank based on the player's EHB using the ranges defined in ranks.ini.
    Ranges can be specified either as a range (e.g. "0-10") or as a lower bound (e.g. "1500+").
    """
    try:
        rank_config = configparser.ConfigParser()
        rank_config.read(ranks_file)
        for range_key, rank_name in rank_config['Group Ranking'].items():
            if '+' in range_key:
                lower_bound = int(range_key.replace('+', ''))
                if ehb >= lower_bound:
                    return rank_name
            else:
                lower_bound, upper_bound = map(int, range_key.split('-'))
                if lower_bound <= ehb < upper_bound:
                    return rank_name
    except Exception as e:
        log(f"Error reading ranks.ini: {e}")
    return "Unknown"

# ------------------------------------------------------------------------------
# Discord Events and Tasks
# ------------------------------------------------------------------------------

@discord_client.event
async def on_ready():
    log(f"Logged in as {discord_client.user}")

    # Start Wise Old Man client session
    await wom_client.start()

    # Run initial member and ranks listing if enabled
    if RUN_AT_STARTUP:
        log("Running list_all_members_and_ranks at startup.")
        await list_all_members_and_ranks()

    # Start the periodic rank-checking task if not already running
    if not check_for_rank_changes.is_running():
        log("Starting check_for_rank_changes task.")
        check_for_rank_changes.start()
    else:
        log("check_for_rank_changes task is already running.")

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_for_rank_changes():
    try:
        log("Starting player comparison...")
        ranks_data = load_ranks()

        if DEBUG:
            log("Debug mode on ")

        result = await wom_client.groups.get_details(GROUP_ID)
        if result.is_ok:
            group = result.unwrap()
            log(f"Fetched group details successfully. Next comparison in {CHECK_INTERVAL / 60:.0f} minutes.")
            for membership in group.memberships:
                try:
                    player = membership.player
                    username = player.display_name
                    ehb = round(player.ehb, 2)
                    rank = get_rank(ehb)
                    
                    # Retrieve last known data
                    last_data = ranks_data.get(username, {})
                    last_ehb = last_data.get("last_ehb", 0)
                    last_rank = last_data.get("rank", "Unknown")
                    
                    # Compare and notify if rank has increased
                    if ehb > last_ehb:
                        await send_rank_up_message(username, rank, last_rank, ehb)
                        log(f"Sent rank up message for {username} with {ehb} EHB for comparison in function.")
                        
                        # Update ranks data and log to CSV if enabled
                        ranks_data[username] = {"last_ehb": ehb, "rank": rank}
                        if PRINT_TO_CSV:
                            log_ehb_to_csv(username, ehb)
                except Exception as e:
                    player_name = getattr(membership.player, "display_name", "Unknown")
                    log(f"Error processing player data for {player_name}: {e}")

            save_ranks(ranks_data)
        else:
            log(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        log(f"Error occurred during rank check: {e}")

async def list_all_members_and_ranks():
    try:
        await wom_client.start()
        result = await wom_client.groups.get_details(GROUP_ID)
        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships
            group_name = group.name

            # Build list of players with EHB > 0
            players = []
            for membership in memberships:
                try:
                    player = membership.player
                    username = player.display_name
                    ehb = round(player.ehb, 2)
                    if ehb > 0:
                        rank = get_rank(ehb)
                        players.append((username, rank, ehb))
                except Exception as e:
                    player_name = getattr(membership.player, "display_name", "Unknown")
                    log(f"Error processing player data for {player_name}: {e}")

            # Sort players by EHB descending
            players.sort(key=lambda x: x[2], reverse=True)

            # Prepare messages to fit within Discord's character limits
            message_lines = []
            header = f"**{group_name} Ranking on {datetime.now().strftime('%Y-%m-%d %H:%M')}**\n"
            chunk = [header, "```"]
            chunk.append(f"{'#':<4}{'Player':<20}{'Rank':<15}{'EHB':<10}")
            chunk.append(f"{'-'*50}")

            for index, (username, rank, ehb) in enumerate(players, start=1):
                line = f"{index:<4}{username:<20}{rank:<15}{ehb:<10}"
                if sum(len(l) + 1 for l in chunk) + len(line) + 5 > 2000:
                    chunk.append("```")
                    message_lines.append("\n".join(chunk))
                    chunk = ["```"]
                chunk.append(line)

            if len(chunk) > 1:
                chunk.append("```")
                message_lines.append("\n".join(chunk))

            # Send all message chunks to the configured Discord channel
            channel = discord_client.get_channel(CHANNEL_ID)
            if channel:
                log(f"Sending message to channel: {channel.name}")
                for message in message_lines:
                    await channel.send(message)
            else:
                log(f"Channel with ID {CHANNEL_ID} not found.")
        else:
            log(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        log(f"Error occurred while listing members and ranks: {e}")

async def send_rank_up_message(username, new_rank, old_rank, ehb):
    try:
        if DEBUG:
            log(f"Debug mode: Sending rank up message for {username}.")
            
        ranks_data = load_ranks()
        discord_names = ranks_data.get(username, {}).get("discord_name", [])

        # Ensure discord_names is always a list
        if not isinstance(discord_names, list):
            discord_names = [discord_names] if discord_names else []
        fans_display = "  ".join(discord_names) if discord_names else "0 😭😭😭"

        # Only send message if the rank has changed
        if new_rank != old_rank:
            channel = discord_client.get_channel(CHANNEL_ID)
            if channel:
                if POST_TO_DISCORD:
                    await channel.send(
                        f'🎉 Congratulations **{username}** on moving up to the rank of **{new_rank}** '
                        f'with **{ehb}** EHB! 🎉\n'
                        f'**Fans:** {fans_display}'
                    )
                    log(f"Sent rank up message for {username} to channel: {channel.name}")
            else:
                log(f"Channel with ID {CHANNEL_ID} not found.")
    except Exception as e:
        log(f"Error sending message: {e}")

# ------------------------------------------------------------------------------
# Initialize Additional Commands and Run the Bot
# ------------------------------------------------------------------------------

setup_commands(
    discord_client,
    wom_client,
    GROUP_ID,
    get_rank,
    list_all_members_and_ranks,
    GROUP_PASSCODE,
    send_rank_up_message,
    check_for_rank_changes
)

discord_client.run(DISCORD_TOKEN)