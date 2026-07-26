import configparser
import os
import socket
from datetime import datetime
from discord.ext import tasks, commands
import discord
import asyncio
import aiohttp
import contextlib
from typing import Optional
from wom import Client as BaseClient

from weeklyupdater import start_monthly_reporter, start_weekly_reporter, start_yearly_reporter
from gainstracker import start_gains_snapshotter
from utils.database import (
    count_players,
    import_csv_history,
    init_database,
    upsert_players,
    log_ehp_history,
)
from utils.rank_utils import (
    load_ranks,
    save_ranks,
    get_rank_for_value,
    get_ehp_rank,
    compute_member_update,
    EHB_SECTION,
)
from utils.log_csv import log_ehb_to_csv
from utils.commands import setup_commands
import uvicorn
from web import create_app
from web.services.bot_state import BotState


class Client(BaseClient):
    async def start(self):
        http = self._http
        if not hasattr(http, "_session") or http._session.closed:
            # Prefer IPv4 inside containers where IPv6 DNS answers exist but
            # outbound IPv6 connectivity is not actually configured.
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            http._session = aiohttp.ClientSession(
                connector=connector,
                json_serialize=lambda o: http._encoder.encode(o).decode(),
            )
            http._method_mapping = {
                "GET": http._session.get,
                "POST": http._session.post,
                "PUT": http._session.put,
                "PATCH": http._session.patch,
                "DELETE": http._session.delete,
            }
    
    async def close(self):
        await super().close()

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
    if 'bot_state' in globals() and bot_state is not None:
        bot_state.log_buffer.append(formatted_message)


def get_messageable_channel(channel_id: int) -> Optional[discord.abc.Messageable]:
    channel = discord_client.get_channel(channel_id)
    if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
        return channel
    return None


def _trim_response_preview(body: str, limit: int = 220) -> str:
    """Return a single-line response preview suitable for logs."""
    preview = " ".join(body.split())
    if len(preview) > limit:
        return preview[:limit] + "..."
    return preview


async def diagnose_group_details_fetch() -> str:
    """Fetch group details directly to expose HTTP status/body on client decode errors."""
    url = f"https://api.wiseoldman.net/v2/groups/{group_id}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "WOMupdtr diagnostics",
        "x-user-agent": "WOMupdtr diagnostics",
    }
    if api_key:
        headers["x-api-key"] = api_key

    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as response:
                body = await response.text(errors="replace")
                content_type = response.headers.get("content-type", "unknown")
                preview = _trim_response_preview(body)
                return (
                    f"WOM group details HTTP {response.status} ({content_type}); "
                    f"body starts with: {preview!r}"
                )
    except Exception as diagnostic_error:
        return f"WOM group details diagnostic request failed: {diagnostic_error}"


# Configuration Loading


config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_file)

# Discord and Wise Old Man settings
discord_token       = config['discord']['token']
channel_id          = int(config['discord']['channel_id'])
weekly_channel_id   = int(config['discord'].get('weekly_channel_id', 0) or 0)
monthly_channel_id  = int(config['discord'].get('monthly_channel_id', weekly_channel_id) or 0)
yearly_channel_id   = int(config['discord'].get('yearly_channel_id', weekly_channel_id) or 0)
gains_channel_id    = int(config['discord'].get('gains_channel_id', 0) or 0)
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
track_ehp           = config['settings'].getboolean('track_ehp', False)
gains_snapshot_interval = int(config['settings'].get('gains_snapshot_interval', 86400) or 86400)
gains_window_days   = int(config['settings'].get('gains_window_days', 7) or 7)
gains_metrics       = [m.strip() for m in config['settings'].get('gains_metrics', 'overall,ehb').split(',') if m.strip()]

# Web interface settings
web_enabled = config['web'].getboolean('enabled', False) if config.has_section('web') else False
web_host = config['web'].get('host', '0.0.0.0') if config.has_section('web') else '0.0.0.0'
web_port = int(config['web'].get('port', '8080')) if config.has_section('web') else 8080

if api_key:
    log("Wise Old Man API key loaded.")
else:
    log("Wise Old Man API key not configured; using default rate limits.")


# Discord Client and Wise Old Man Client Initialization


class IPv4Bot(commands.Bot):
    """Bot subclass that forces IPv4 for outbound connections."""
    async def setup_hook(self):
        # Must be created inside the event loop; forces IPv4 so containers
        # without working IPv6 can reach discord.com
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self.http.connector = connector
        await super().setup_hook()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
# Use slash commands via app commands; prefix commands are disabled
discord_client = IPv4Bot(command_prefix=commands.when_mentioned, intents=intents)

wom_client = Client(api_key=api_key)

weekly_report_task = None
monthly_report_task = None
yearly_report_task = None
gains_snapshot_task = None


# Utility Functions


def get_rank(ehb, ranks_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ranks.ini')):
    """
    Determines the rank based on the player's EHB using the ranges defined in ranks.ini.
    Ranges can be specified either as a range (e.g. "0-10") or as a lower bound (e.g. "1500+").

    Thin wrapper over the consolidated ``rank_utils`` parser (single source of truth).
    """
    return get_rank_for_value(ehb, EHB_SECTION, ranks_file)


# Discord Events and Tasks


@discord_client.event
async def on_ready():
    log(f"Logged in as {discord_client.user}")

    # Register slash commands with Discord
    await discord_client.tree.sync()

    # Start Wise Old Man client session
    await wom_client.start()

    global weekly_report_task
    global monthly_report_task
    global yearly_report_task
    global gains_snapshot_task
    if gains_snapshot_task is None:
        if gains_channel_id or gains_metrics:
            gains_snapshot_task = start_gains_snapshotter(
                wom_client=wom_client,
                discord_client=discord_client,
                group_id=group_id,
                channel_id=gains_channel_id,
                metrics=gains_metrics,
                window_days=gains_window_days,
                interval_seconds=gains_snapshot_interval,
                log=log,
                on_snapshot=lambda: setattr(bot_state, "last_gains_snapshot", datetime.now()),
                debug=debug,
            )
            log("Gains snapshot task started.")
        else:
            log("gains snapshot disabled (no metrics/channel configured).")

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

    if monthly_report_task is None:
        if monthly_channel_id:
            monthly_report_task = start_monthly_reporter(
                wom_client=wom_client,
                discord_client=discord_client,
                group_id=group_id,
                channel_id=monthly_channel_id,
                log=log,
                debug=debug,
            )
            log("Monthly report task started.")
        else:
            log("monthly_channel_id not configured; monthly report disabled.")

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
        try:
            result = await wom_client.groups.get_details(group_id)
        except Exception as fetch_error:
            diagnostic = await diagnose_group_details_fetch()
            log(f"Failed to fetch group details: {fetch_error}. {diagnostic}")
            return

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
                    player_exp = getattr(player, "exp", None)
                    total_xp = int(player_exp) if player_exp is not None else None

                    last_data = ranks_data.get(username, {})

                    ehp = None
                    ehp_rank = None
                    if track_ehp:
                        ehp = round(getattr(player, "ehp", 0) or 0, 2)
                        ehp_rank = get_ehp_rank(ehp)

                    # Independent EHB / EHP evaluation merged into one entry.
                    result = compute_member_update(
                        last_data,
                        ehb,
                        rank,
                        ehp=ehp,
                        ehp_rank=ehp_rank,
                        track_ehp=track_ehp,
                        total_xp=total_xp,
                    )

                    # --- EHB side effects ---
                    if result["ehb_increase"]:
                        last_ehb = last_data.get("last_ehb", 0)
                        log(f"Player {username} EHB increased from {last_ehb:.2f} to {ehb:.2f}")
                        await send_rank_up_message(username, rank, result["ehb_old_rank"], ehb)
                        if debug:
                            log(f"Sent rank up message for {username} with {ehb} EHB for comparison in function.")
                        if print_to_csv:
                            log_ehb_to_csv(username, ehb)
                    elif rank != result["ehb_old_rank"]:
                        log(f"Correcting stale rank for {username}: '{result['ehb_old_rank']}' -> '{rank}'")

                    # --- EHP side effects ---
                    if track_ehp and result["ehp_increase"]:
                        log(f"Player {username} EHP increased to {ehp:.2f}")
                        await send_rank_up_message(
                            username, ehp_rank, result["ehp_old_rank"], ehp, metric_label="EHP"
                        )
                        log_ehp_history(username, ehp)

                    ranks_data[username] = result["entry"]

                except Exception as e:
                    player_name = getattr(membership.player, "display_name", "Unknown")
                    log(f"Error processing player data for {player_name}: {e}")

            save_ranks(ranks_data)
            log("Rank check completed successfully!")
            bot_state.last_rank_check = datetime.now()

        else:
            log(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        log(f"Error occurred during rank check: {e}")

async def list_all_members_and_ranks():
    try:
        await wom_client.start()
        try:
            result = await wom_client.groups.get_details(group_id)
        except Exception as fetch_error:
            diagnostic = await diagnose_group_details_fetch()
            log(f"Failed to fetch group details: {fetch_error}. {diagnostic}")
            return

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
    msg = "❌ Failed to refresh group: unknown error."

    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    updated_count = data.get("count", 0)
                    if updated_count > 0:
                        msg = f"✅ Successfully refreshed group data. {updated_count} members updated."
                    else:
                        msg = "ℹ️ Group data is already up to date."
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
    bot_state.last_group_refresh = datetime.now()
    if post_to_discord and msg.startswith("❌"):
        channel = get_messageable_channel(channel_id)
        if channel:
            await channel.send(msg)

async def send_rank_up_message(username, new_rank, old_rank, ehb, metric_label="EHB"):
    try:
        if debug:
            log(f"debug mode: Sending rank up message for {username}.")

        # Only send message if the rank has changed
        if new_rank != old_rank:
            channel = get_messageable_channel(channel_id)
            if channel:
                if post_to_discord:
                    await channel.send(
                        f'🎉 Congratulations **{username}** on moving up to the rank of **{new_rank}** '
                        f'with **{ehb}** {metric_label}! 🎉'
                    )
                    log(f"Sent rank up message for {username} to channel: {channel}")
            else:
                log(f"Channel with ID {channel_id} not found.")
    except Exception as e:
        log(f"Error sending message: {e}")


# Shared state for web interface
bot_state = BotState(
    wom_client=wom_client,
    discord_client=discord_client,
    group_id=group_id,
    group_passcode=group_passcode,
    get_rank=get_rank,
    check_interval=check_interval,
    post_to_discord=post_to_discord,
    silent=silent,
    debug=debug,
)


# Initialize Additional Commands


setup_commands(
    discord_client,
    wom_client,
    group_id,
    weekly_channel_id,
    monthly_channel_id,
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
                bot_state.list_all_members_and_ranks = list_all_members_and_ranks
                bot_state.check_for_rank_changes = check_for_rank_changes
                bot_state.refresh_group_data = refresh_group_data
                bot_state.log_func = log
                bot_state.bot_started_at = datetime.now()
                db_path = init_database()
                log(f"SQLite database ready at {db_path}")

                ranks_snapshot = load_ranks()
                if ranks_snapshot:
                    upsert_players(ranks_snapshot, db_path=db_path)
                imported_rows = import_csv_history(db_path=db_path)
                if imported_rows:
                    log(f"Imported {imported_rows} EHB history rows into SQLite.")
                elif count_players(db_path=db_path) == 0 and not ranks_snapshot:
                    log("SQLite database initialized with no existing rank or EHB history data.")

                tasks_to_run = [discord_client.start(discord_token)]

                if web_enabled:
                    web_app = create_app(bot_state, host=web_host, port=web_port, log_func=log)
                    uvi_config = uvicorn.Config(
                        web_app, host=web_host, port=web_port, log_level="info"
                    )
                    server = uvicorn.Server(uvi_config)
                    tasks_to_run.append(server.serve())

                await asyncio.gather(*tasks_to_run)
        
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
