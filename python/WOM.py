import configparser
import os
from datetime import datetime
from discord.ext import tasks, commands
import discord
import asyncio
import aiohttp
import contextlib
import sys
from typing import Optional
from wom import Client as BaseClient

from weeklyupdater import start_weekly_reporter, start_yearly_reporter
from utils.rank_utils import load_ranks, save_ranks
from utils.log_csv import log_ehb_to_csv
from utils.commands import setup_commands


class Client(BaseClient):
    def __init__(self, api_key: str | None = None):
        self._session = None
        self._connector = None
        super().__init__(api_key=api_key)
    
    async def start(self):
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector()
            self._session = aiohttp.ClientSession(connector=self._connector)
        return await super().start()
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        if self._connector and not self._connector.closed:
            await self._connector.close()
            self._connector = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Helper Functions


def log(message: str):
    """Logs a message with the current timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{timestamp} - {message}"
    print(formatted_message)  # Print to terminal
    
    # Send to GUI if it's running
    botgui_module = sys.modules.get('gui') or sys.modules.get('__main__')
    if botgui_module and hasattr(botgui_module, 'BotGUI'):
        try:
            botgui_module.BotGUI.msg_queue.put(formatted_message)
        except Exception as e:
            print(f"Failed to send message to GUI: {e}")


def get_messageable_channel(channel_id: int) -> Optional[discord.abc.Messageable]:
    channel = discord_client.get_channel(channel_id)
    if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
        return channel
    return None


# Configuration Loading


config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_file)

# Discord and Wise Old Man settings
discord_token       = config['discord']['token']
channel_id          = int(config['discord']['channel_id'])
weekly_channel_id   = int(config['discord'].get('weekly_channel_id', 0) or 0)
yearly_channel_id   = int(config['discord'].get('yearly_channel_id', weekly_channel_id) or 0)
group_id            = int(config['wiseoldman']['group_id'])
group_passcode      = config['wiseoldman']['group_passcode']
api_key             = config['wiseoldman'].get('api_key', '').strip() or None
check_interval      = int(config['settings']['check_interval'])
run_at_startup      = config['settings'].getboolean('run_at_startup', True)
print_to_csv        = config['settings'].getboolean('print_to_csv', True)
print_csv_changes   = config['settings'].getboolean('print_csv_changes', True)
post_to_discord     = config['settings'].getboolean('post_to_discord', True)
silent              = config['settings'].getboolean('silent', False)
debug               = config['settings'].getboolean('debug', False)

if api_key:
    log("Wise Old Man API key loaded.")
else:
    log("Wise Old Man API key not configured; using default rate limits.")


# Discord Client and Wise Old Man Client Initialization


intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
# Use slash commands via app commands; prefix commands are disabled
discord_client = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

wom_client = Client(api_key=api_key)

weekly_report_task = None
yearly_report_task = None


# Utility Functions


def get_rank(ehb, ranks_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ranks.ini')):
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


# Discord Events and Tasks


@discord_client.event
async def on_ready():
    log(f"Logged in as {discord_client.user}")

    # Register slash commands with Discord
    await discord_client.tree.sync()

    # Start Wise Old Man client session
    await wom_client.start()

    global weekly_report_task
    global yearly_report_task
    if weekly_report_task is None:
        if weekly_channel_id:
            weekly_report_task = start_weekly_reporter(
                wom_client=wom_client,
                discord_client=discord_client,
                group_id=group_id,
                channel_id=weekly_channel_id,
                log=log,
                debug=debug,
            )
            log("Weekly report task started.")
        else:
            log("weekly_channel_id not configured; weekly report disabled.")

    if yearly_report_task is None:
        if yearly_channel_id:
            yearly_report_task = start_yearly_reporter(
                wom_client=wom_client,
                discord_client=discord_client,
                group_id=group_id,
                channel_id=yearly_channel_id,
                log=log,
                debug=debug,
            )
            log("Yearly report task started.")
        else:
            log("yearly_channel_id not configured; yearly report disabled.")

    # Run initial member and ranks listing if enabled
    if run_at_startup:
        log("Running list_all_members_and_ranks at startup.")
        await list_all_members_and_ranks()

    # Start the periodic rank-checking task if not already running
    if not check_for_rank_changes.is_running():
        if debug:
            log("Starting check_for_rank_changes task.")
        check_for_rank_changes.start()
    else:
        log("check_for_rank_changes task is already running.")

    # Start the periodic group refresh task if not already running
    if not refresh_group_task.is_running():
        if debug:
            log("Starting refresh_group_task.")
        refresh_group_task.start()
    else:
        log("refresh_group_task is already running.")

@tasks.loop(seconds=check_interval)
async def check_for_rank_changes():
    try:
        if debug:
            log("debug mode on ")
            log("Starting player comparison...")
        ranks_data = load_ranks()
        result = await wom_client.groups.get_details(group_id)
        if result.is_ok:
            group = result.unwrap()
            if not silent:
                log(f"Fetched group details successfully. Next comparison in {check_interval / 60:.0f} minutes.")
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
                        log(f"Player {username} EHB increased from {last_ehb:.2f} to {ehb:.2f}")
                        await send_rank_up_message(username, rank, last_rank, ehb)
                        if debug:
                            log(f"Sent rank up message for {username} with {ehb} EHB for comparison in function.")

                        # Update ranks data and log to CSV if enabled
                        ranks_data[username] = {"last_ehb": ehb, "rank": rank}
                        if print_to_csv:
                            log_ehb_to_csv(username, ehb)


                except Exception as e:
                    player_name = getattr(membership.player, "display_name", "Unknown")
                    log(f"Error processing player data for {player_name}: {e}")

            save_ranks(ranks_data)
            log("Rank check completed successfully!")
            
        else:
            log(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        log(f"Error occurred during rank check: {e}")

async def list_all_members_and_ranks():
    try:
        await wom_client.start()
        result = await wom_client.groups.get_details(group_id)
        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships
            group_name = group.name

            # Build list of players including those with 0 EHB
            players = []
            for membership in memberships:
                try:
                    player = membership.player
                    username = player.display_name
                    ehb = round(player.ehb, 2)
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
            channel = get_messageable_channel(channel_id)
            if channel:
                log(f"Sending message to channel: {channel}")
                for message in message_lines:
                    await channel.send(message)  
            else:
                log(f"Channel with ID {channel_id} not found.")
        else:
            log(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        log(f"Error occurred while listing members and ranks: {e}")

async def refresh_group_data():
    """Refreshes the group's data using the WiseOldMan API."""
    url = f"https://api.wiseoldman.net/v2/groups/{group_id}/update-all"
    headers = {"Content-Type": "application/json"}
    payload = {"verificationCode": group_passcode}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    updated_count = data.get("count", 0)
                    # if updated_count > 0:
                    #     msg = f"✅ Successfully refreshed group data. {updated_count} members updated."
                    # else:
                    #     msg = "ℹ️ Group data is already up to date."
                elif response.status == 400:
                    error_message = await response.json()
                    if error_message.get("message") == "Nothing to update.":
                        msg = "ℹ️ The API reported 'Nothing to update'."
                    else:
                        msg = f"❌ Failed to refresh group: {error_message}"
                else:
                    error_message = await response.text()
                    msg = f"❌ Failed to refresh group: {error_message}"
    except Exception as e:
        msg = f"❌ Error refreshing WiseOldMan group: {e}"

    log(msg)
    return msg

@tasks.loop(seconds=check_interval * 48)
async def refresh_group_task():
    msg = await refresh_group_data()
    if post_to_discord:
        channel = get_messageable_channel(channel_id)
        if channel:
            await channel.send(msg)  

async def send_rank_up_message(username, new_rank, old_rank, ehb):
    try:
        if debug:
            log(f"debug mode: Sending rank up message for {username}.")

        ranks_data = load_ranks()
        discord_names = ranks_data.get(username, {}).get("discord_name", [])

        # Ensure discord_names is always a list
        if not isinstance(discord_names, list):
            discord_names = [discord_names] if discord_names else []
        fans_display = "  ".join(discord_names) if discord_names else "0 😭😭😭"

        # Only send message if the rank has changed
        if new_rank != old_rank:
            channel = get_messageable_channel(channel_id)
            if channel:
                if post_to_discord:
                    await channel.send(  
                        f'🎉 Congratulations **{username}** on moving up to the rank of **{new_rank}** '
                        f'with **{ehb}** EHB! 🎉\n'
                        f'**Fans:** {fans_display}'
                    )
                    log(f"Sent rank up message for {username} to channel: {channel}")
            else:
                log(f"Channel with ID {channel_id} not found.")
    except Exception as e:
        log(f"Error sending message: {e}")


# Initialize Additional Commands


setup_commands(
    discord_client,
    wom_client,
    group_id,
    weekly_channel_id,
    yearly_channel_id,
    get_rank,
    list_all_members_and_ranks,
    send_rank_up_message,
    check_for_rank_changes,
    refresh_group_data,
    log,
    debug
)


# Run the Bot


if __name__ == "__main__":
    try:
        # Create event loop for the main thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def main():
            async with wom_client, contextlib.AsyncExitStack() as stack:
                await discord_client.start(discord_token)
                try:
                    await asyncio.Future()  # run forever
                except asyncio.CancelledError:
                    await discord_client.close()
        
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            print(f"Error during final cleanup: {e}")
        print("Cleanup complete. Goodbye!")
