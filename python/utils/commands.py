"""Discord slash command definitions.

This module registers the bot's commands using Discord's modern *Interactions*
API (slash commands). Slash commands provide built-in auto-completion and are
the recommended way for bots to interact with users.
"""

from datetime import datetime, timezone
import os
import socket
from typing import Optional

import aiohttp
from discord import app_commands, Interaction
from discord.ext import commands

from .rank_utils import (
    load_ranks,
    merge_manual_rank_update,
    next_rank,
    next_rank_ehp,
    save_ranks,
)
from gainstracker import build_gains_lines, collect_gains_leaderboard, resolve_metric
from weeklyupdater import (
    generate_monthly_report_messages,
    generate_weekly_report_messages,
    generate_yearly_report_messages,
    most_recent_month_end,
    most_recent_year_end,
    most_recent_week_end,
    send_monthly_report,
    send_yearly_report,
    send_weekly_report,
    write_yearly_report_file,
)


def _chunk_code_block(lines: list[str], limit: int = 1990) -> list[str]:
    """Wrap table lines in ``` code blocks, splitting to stay under Discord's cap."""
    messages: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            messages.append("```\n" + "\n".join(current) + "\n```")

    for line in lines:
        tentative = "\n".join(current + [line])
        if len(tentative) + 8 > limit and current:
            flush()
            current.clear()
        current.append(line)
    flush()

    return messages or ["```\n(no data)\n```"]


def _format_lookup_message(username: str, user_data: dict) -> str:
    """Format locally persisted rank metrics for the Discord lookup response."""
    ehb = user_data["last_ehb"]
    rank = user_data["rank"]
    message = f"**{username}**\n**Rank:** {rank} ({ehb} EHB)"
    if "ehp_rank" in user_data:
        ehp = user_data.get("last_ehp", 0)
        ehp_rank = user_data.get("ehp_rank", "Unknown")
        message += f"\n**Skilling Rank:** {ehp_rank} ({ehp} EHP)"

    total_xp = user_data.get("total_xp")
    if total_xp is None:
        xp_display = "Not available yet (run a rank refresh)"
    else:
        try:
            xp_display = f"{int(total_xp):,}"
        except (TypeError, ValueError):
            xp_display = "Not available yet (run a rank refresh)"
    return f"{message}\n**Total XP:** {xp_display}"


def setup_commands(
    bot: commands.Bot,
    wom_client,
    GROUP_ID: int,
    weekly_channel_id: int,
    monthly_channel_id: int,
    yearly_channel_id: int,
    get_rank,
    list_all_members_and_ranks,
    send_rank_up_message,
    check_for_rank_changes,
    refresh_group_func,
    log,
    debug: bool,
    reports_enabled: bool = True,
):
    """Register slash commands on the provided bot."""

    _REPORTS_DISABLED_MESSAGE = (
        "❌ Weekly/monthly/yearly reports are temporarily disabled "
        "(see REPORTS_ENABLED in WOM.py)."
    )

    # Command: /lookup --- Lists locally persisted rank metrics for a specific user.

    @bot.tree.command(name="lookup", description="Lists rank, EHB, EHP, and total XP for a user.")
    @app_commands.describe(username="Wise Old Man username")
    async def lookup(interaction: Interaction, username: str):
        try:
            ranks_data = load_ranks()
            if username in ranks_data:
                user_data = ranks_data[username]
                ehb = user_data["last_ehb"]
                rank = user_data["rank"]
                message = _format_lookup_message(username, user_data)
                await interaction.response.send_message(message)
                if debug:
                    print(f"Listed {username}: {rank} ({ehb} EHB)")
            else:
                await interaction.response.send_message(
                    f"❌ Username **'{username}'** not found in the ranks data.",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while linking: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /lookup command: {e}")

    # Command: /refresh --- Refreshes and posts the updated group rankings.

    @bot.tree.command(name="refresh", description="Refreshes and posts the updated group rankings.")
    async def refresh(interaction: Interaction):
        try:
            await list_all_members_and_ranks()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if debug:
                print(f"{timestamp} - Refreshed rankings via Discord Command.")
            await interaction.response.send_message("✅ Refreshed rankings.")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error refreshing rankings: {e}", ephemeral=True
            )

    # Command: /forcecheck --- Forces check_for_rank_changes to run.

    @bot.tree.command(name="forcecheck", description="Forces check_for_rank_changes to run.")
    async def forcecheck(interaction: Interaction):
        try:
            await check_for_rank_changes()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if debug:
                print(f"{timestamp} - Forced check_for_rank function.")
            await interaction.response.send_message("✅ Forced rank check.")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error refreshing rankings: {e}", ephemeral=True
            )

    # Command: /update --- Fetches and updates the rank for a specific user by searching the group data.

    @bot.tree.command(name="update", description="Fetches and updates the rank for a specific user.")
    @app_commands.describe(username="Wise Old Man username")
    async def update(interaction: Interaction, username: str):
        try:
            # Ensure the Wise Old Man client's session is started
            await wom_client.start()

            # Fetch group details
            result = await wom_client.groups.get_details(GROUP_ID)

            if result.is_ok:
                group = result.unwrap()
                # Search for the player in the group memberships (case-insensitive)
                player = next(
                    (
                        member.player
                        for member in group.memberships
                        if member.player.display_name.lower() == username.lower()
                    ),
                    None,
                )

                if player:
                    ranks_data = load_ranks()
                    ehb = round(player.ehb, 2)
                    rank = get_rank(ehb)

                    # Update ranks_data
                    rank_key = next(
                        (
                            stored_username
                            for stored_username in ranks_data
                            if stored_username.lower() == username.lower()
                        ),
                        username,
                    )
                    ranks_data[rank_key] = merge_manual_rank_update(
                        ranks_data.get(rank_key, {}), ehb, rank
                    )
                    save_ranks(ranks_data)

                    # Send formatted message to Discord
                    await interaction.response.send_message(
                        f"✅ **{player.display_name}** \n**Rank:** {rank} ({ehb} EHB)"
                    )
                    if debug:
                        print(f"Updated {player.display_name}: {rank} ({ehb} EHB)")
                else:
                    await interaction.response.send_message(
                        f"❌ Could not find a player with username **{username}** in the group.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    f"❌ Failed to fetch group details: {result.unwrap_err()}",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error updating {username}: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /update command: {e}")

    # Command: /refreshgroup --- Forces a full update for the group's data using the WiseOldMan API.

    @bot.tree.command(name="refreshgroup", description="Forces a full update for the group's data.")
    async def refreshgroup(interaction: Interaction):
        try:
            message = await refresh_group_func()
            await interaction.response.send_message(message)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error refreshing WiseOldMan group: {e}", ephemeral=True
            )

    # Command: /weeklyupdate --- Posts the weekly report to the weekly channel.

    @bot.tree.command(name="weeklyupdate", description="Posts the weekly report to the weekly channel.")
    async def weeklyupdate(interaction: Interaction):
        if not reports_enabled:
            await interaction.response.send_message(_REPORTS_DISABLED_MESSAGE, ephemeral=True)
            return
        if not weekly_channel_id:
            await interaction.response.send_message(
                "❌ weekly_channel_id not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            end_date = most_recent_week_end(datetime.now(timezone.utc))
            messages = await generate_weekly_report_messages(
                wom_client=wom_client,
                group_id=GROUP_ID,
                end_date=end_date,
                log=log,
            )
            await send_weekly_report(
                discord_client=bot,
                channel_id=weekly_channel_id,
                messages=messages,
                log=log,
            )
            await interaction.followup.send("✅ Weekly report sent.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error sending weekly report: {e}", ephemeral=True
            )

    # Command: /monthlyreport --- Posts the monthly report to the monthly channel.

    @bot.tree.command(name="monthlyreport", description="Posts the most recent completed monthly report.")
    async def monthlyreport(interaction: Interaction):
        if not reports_enabled:
            await interaction.response.send_message(_REPORTS_DISABLED_MESSAGE, ephemeral=True)
            return
        if not monthly_channel_id:
            await interaction.response.send_message(
                "❌ monthly_channel_id not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            end_date = most_recent_month_end(datetime.now(timezone.utc))
            messages = await generate_monthly_report_messages(
                wom_client=wom_client,
                group_id=GROUP_ID,
                end_date=end_date,
                log=log,
            )
            await send_monthly_report(
                discord_client=bot,
                channel_id=monthly_channel_id,
                messages=messages,
                log=log,
            )
            await interaction.followup.send("✅ Monthly report sent.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error sending monthly report: {e}", ephemeral=True
            )

    # Command: /yearlyreport --- Posts the yearly report to the yearly channel.

    @bot.tree.command(name="yearlyreport", description="Posts the yearly report to the yearly channel.")
    @app_commands.describe(year="Report year (2020 to last completed year).")
    async def yearlyreport(interaction: Interaction, year: Optional[int] = None):
        if not reports_enabled:
            await interaction.response.send_message(_REPORTS_DISABLED_MESSAGE, ephemeral=True)
            return
        if not yearly_channel_id:
            await interaction.response.send_message(
                "❌ yearly_channel_id not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            now = datetime.now(timezone.utc)
            latest_end = most_recent_year_end(now)
            last_completed_year = latest_end.year - 1

            if year is not None and (year < 2020 or year > last_completed_year):
                await interaction.followup.send(
                    f"❌ Year must be between 2020 and {last_completed_year}.",
                    ephemeral=True,
                )
                return

            end_date = latest_end if year is None else datetime(year + 1, 1, 1, 12, 0, tzinfo=timezone.utc)
            messages = await generate_yearly_report_messages(
                wom_client=wom_client,
                group_id=GROUP_ID,
                end_date=end_date,
                log=log,
            )
            await send_yearly_report(
                discord_client=bot,
                channel_id=yearly_channel_id,
                messages=messages,
                log=log,
            )
            await interaction.followup.send("✅ Yearly report sent.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error sending yearly report: {e}", ephemeral=True
            )

    # Command: /yearlyreportfile --- Writes the yearly report to a local file.

    @bot.tree.command(
        name="yearlyreportfile",
        description="Writes the yearly report to a local file for debugging.",
    )
    @app_commands.describe(
        year="Report year (2020 to last completed year).",
        filename="Optional output filename (saved in the python folder).",
    )
    async def yearlyreportfile(
        interaction: Interaction,
        year: Optional[int] = None,
        filename: Optional[str] = None,
    ):
        if not reports_enabled:
            await interaction.response.send_message(_REPORTS_DISABLED_MESSAGE, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        try:
            now = datetime.now(timezone.utc)
            latest_end = most_recent_year_end(now)
            last_completed_year = latest_end.year - 1

            if year is not None and (year < 2020 or year > last_completed_year):
                await interaction.followup.send(
                    f"❌ Year must be between 2020 and {last_completed_year}.",
                    ephemeral=True,
                )
                return

            end_date = (
                latest_end
                if year is None
                else datetime(year + 1, 1, 1, 12, 0, tzinfo=timezone.utc)
            )
            report_year = end_date.year - 1
            output_name = filename or f"yearly_report_{report_year}.txt"
            output_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", output_name)
            )

            messages = await generate_yearly_report_messages(
                wom_client=wom_client,
                group_id=GROUP_ID,
                end_date=end_date,
                log=log,
            )
            await write_yearly_report_file(
                output_path=output_path,
                messages=messages,
                log=log,
            )
            await interaction.followup.send(
                f"✅ Yearly report written to `{output_path}`.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error writing yearly report: {e}", ephemeral=True
            )

    # Command: /commands --- Lists all available commands.

    @bot.tree.command(name="commands", description="Lists all available commands.")
    async def commands_list(interaction: Interaction):
        command_list = [
            "**Usernames with spaces in them need to be enclosed in quotes.**",
            "Usernames are case-sensitive except for **/update** command",
            "\n",
            "/refresh ➡️    Refreshes and posts the updated group rankings.",
            "/update 'username' ➡️  Fetches and updates the rank for a specific user.",
            "/rankup 'username' ➡️  Displays the current rank, EHB, and next rank for a given player.",
            "/refreshgroup ➡️   Forces a full update for the group's data.",
            "/lookup 'username' ➡️  Lists the rank and EHB for a specific user.",
            "/commands ➡️   Lists all available commands.",
            "/goodnight ➡️  Sends a good night message.",
            "/forcecheck ➡️     Forces check_for_rank_changes task to run.",
            "/weeklyupdate ➡️   Posts the weekly report to the weekly channel.",
            "/monthlyreport ➡️   Posts the last completed monthly report.",
            "/yearlyreport [year] ➡️   Posts the yearly report to the yearly channel.",
            "/yearlyreportfile [year] [filename] ➡️   Writes the yearly report to a local file.",
            "/sendrankup_debug ➡️   Debugging command to simulate a rank up message.",
            "/debug_group ➡️    Debugs and inspects group response.",
        ]
        await interaction.response.send_message(
            "**Available Commands:**\n" + "\n".join(command_list), ephemeral=True
        )

    # Command: /goodnight --- Sends a good night message.

    @bot.tree.command(name="goodnight", description="Sends a good night message.")
    async def goodnight(interaction: Interaction):
        await interaction.response.send_message("Good night, king 👑")

    # Command: /debug_group --- Debugging command to inspect the group response.

    @bot.tree.command(name="debug_group", description="Debugs and inspects group response.")
    async def debug_group(interaction: Interaction):
        url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        group_data = await response.json()
                        group_name = group_data.get("name", "Unknown")
                        member_count = len(group_data.get("memberships", []))
                        await interaction.response.send_message(
                            f"Group Name: {group_name}\nMembers: {member_count}"
                        )
                        # Log the full group data for manual inspection
                        if debug:
                            print(group_data)
                    else:
                        error_message = await response.text()
                        await interaction.response.send_message(
                            f"Failed to fetch group details: {error_message}",
                            ephemeral=True,
                        )
        except Exception as e:
            await interaction.response.send_message(
                f"Error fetching group details: {e}", ephemeral=True
            )

    # Command: /sendrankup_debug --- Debugging command to simulate a rank up message.

    @bot.tree.command(name="sendrankup_debug", description="Debug command to simulate a rank up message.")
    async def sendrankup_debug(interaction: Interaction):
        try:
            # Using fixed test values for debugging
            test_username = "Zezima"
            new_rank = "Legend"
            old_rank = "Hero"
            ehb = 1000000000
            await send_rank_up_message(test_username, new_rank, old_rank, ehb)
            await interaction.response.send_message(
                "✅ Successfully sent a rank up message to the channel."
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error sending a rank up message to the channel: {e}",
                ephemeral=True,
            )

    # Command: /rankup --- Displays the current rank, EHB, and next rank for a given player.

    @bot.tree.command(
        name="rankup",
        description="Displays the current rank, EHB, and next rank for a player.",
    )
    @app_commands.describe(username="Wise Old Man username")
    async def rankup(interaction: Interaction, username: str):
        try:
            ranks_data = load_ranks()
            if username not in ranks_data:
                await interaction.response.send_message(
                    f"❌ Username '{username}' not found in the ranks data.",
                    ephemeral=True,
                )
                return

            user_data = ranks_data[username]
            current_rank = user_data.get("rank", "Unknown")
            current_ehb = user_data.get("last_ehb", 0)
            next_rank_info = next_rank(username)

            message = (
                f"🔹 **Player:** {username}\n"
                f"🏅 **Current Rank:** {current_rank} ({current_ehb} EHB)\n"
                f"📈 **Next Rank:** {next_rank_info}"
            )
            if "ehp_rank" in user_data:
                current_ehp_rank = user_data.get("ehp_rank", "Unknown")
                current_ehp = user_data.get("last_ehp", 0)
                message += (
                    f"\n⛏️ **Current Skilling Rank:** {current_ehp_rank} ({current_ehp} EHP)\n"
                    f"📈 **Next Skilling Rank:** {next_rank_ehp(username)}"
                )
            await interaction.response.send_message(message)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /rankup command: {e}")

    # Command: /ehpladder --- Lists players ranked by EHP (skilling).

    @bot.tree.command(
        name="ehpladder",
        description="Lists players ranked by EHP (skilling efficiency).",
    )
    async def ehpladder(interaction: Interaction):
        try:
            ranks_data = load_ranks()
            players = [
                (
                    username,
                    data.get("ehp_rank", "Unknown"),
                    round(float(data.get("last_ehp", 0) or 0), 2),
                )
                for username, data in ranks_data.items()
            ]
            players = [entry for entry in players if entry[2] > 0]
            players.sort(key=lambda entry: entry[2], reverse=True)

            if not players:
                await interaction.response.send_message(
                    "❌ No EHP data available yet. Enable `track_ehp` and let the bot run a check.",
                    ephemeral=True,
                )
                return

            lines = [f"{'#':<4}{'Player':<20}{'Skill Rank':<15}{'EHP':<10}", "-" * 50]
            for index, (username, ehp_rank, ehp) in enumerate(players, start=1):
                lines.append(f"{index:<4}{username:<20}{ehp_rank:<15}{ehp:<10}")

            messages = _chunk_code_block(lines)
            await interaction.response.send_message(messages[0])
            for extra in messages[1:]:
                await interaction.followup.send(extra)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /ehpladder command: {e}")

    # Command: /gains --- Live leaderboard of gains for a metric over a period.

    @bot.tree.command(
        name="gains",
        description="Shows the top gainers for a metric over the last N days.",
    )
    @app_commands.describe(
        metric="Metric name (e.g. overall, ehb, sailing, zulrah).",
        days="Look-back window in days (default 7).",
    )
    async def gains(interaction: Interaction, metric: str, days: Optional[int] = 7):
        window_days = days if days and days > 0 else 7
        if resolve_metric(metric) is None:
            await interaction.response.send_message(
                f"❌ Unknown metric '{metric}'. Try `overall`, `ehb`, `sailing`, or a boss name.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            await wom_client.start()
            leaderboard = await collect_gains_leaderboard(
                wom_client=wom_client,
                group_id=GROUP_ID,
                metric_name=metric,
                window_days=window_days,
                log=log,
            )
            lines = build_gains_lines(metric, window_days, leaderboard)
            messages = _chunk_code_block(lines)
            for message in messages:
                await interaction.followup.send(message)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error fetching gains: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /gains command: {e}")
