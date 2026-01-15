"""Discord slash command definitions.

This module registers the bot's commands using Discord's modern *Interactions*
API (slash commands). Slash commands provide built-in auto-completion and are
the recommended way for bots to interact with users.
"""

from datetime import datetime, timezone
import os
from typing import Optional

import aiohttp
from discord import app_commands, Interaction
from discord.ext import commands

from .rank_utils import load_ranks, save_ranks, next_rank
from weeklyupdater import (
    generate_weekly_report_messages,
    generate_yearly_report_messages,
    most_recent_year_end,
    most_recent_week_end,
    send_yearly_report,
    send_weekly_report,
    write_yearly_report_file,
)


# Helper Functions --- Formats the Discord fans for display.

def format_discord_fans(discord_fans):
    if isinstance(discord_fans, list):
        return " + ".join(discord_fans) if discord_fans else "0 😭"
    return discord_fans if discord_fans else "0 😭"


def setup_commands(
    bot: commands.Bot,
    wom_client,
    GROUP_ID: int,
    weekly_channel_id: int,
    yearly_channel_id: int,
    get_rank,
    list_all_members_and_ranks,
    send_rank_up_message,
    check_for_rank_changes,
    refresh_group_func,
    log,
    debug: bool,
):
    """Register slash commands on the provided bot."""

    # Command: /lookup --- Lists the rank and EHB for a specific user.

    @bot.tree.command(name="lookup", description="Lists the rank and EHB for a specific user.")
    @app_commands.describe(username="Wise Old Man username")
    async def lookup(interaction: Interaction, username: str):
        try:
            ranks_data = load_ranks()
            if username in ranks_data:
                ehb = ranks_data[username]["last_ehb"]
                rank = ranks_data[username]["rank"]
                discord_fans = ranks_data[username]["discord_name"]
                fans_display = format_discord_fans(discord_fans)
                await interaction.response.send_message(
                    f"**{username}**\n**Rank:** {rank} ({ehb} EHB)\n**Fans:** {fans_display}"
                )
                if debug:
                    print(f"Listed {username}: {rank} ({ehb} EHB), Fans: {fans_display}")
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

                    # Fetch Discord fans (linked Discord users)
                    discord_fans = ranks_data.get(username, {}).get("discord_name", [])
                    fans_display = format_discord_fans(discord_fans)

                    # Update ranks_data
                    ranks_data[username] = {
                        "last_ehb": ehb,
                        "rank": rank,
                        "discord_name": discord_fans,
                    }
                    save_ranks(ranks_data)

                    # Send formatted message to Discord
                    await interaction.response.send_message(
                        f"✅ **{player.display_name}** \n**Rank:** {rank} ({ehb} EHB)\n**Fans:** {fans_display}"
                    )
                    if debug:
                        print(
                            f"Updated {player.display_name}: {rank} ({ehb} EHB), Fans: {fans_display}"
                        )
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

    # Command: /yearlyreport --- Posts the yearly report to the yearly channel.

    @bot.tree.command(name="yearlyreport", description="Posts the yearly report to the yearly channel.")
    @app_commands.describe(year="Report year (2020 to last completed year).")
    async def yearlyreport(interaction: Interaction, year: Optional[int] = None):
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
            "/link 'username' 'discord_name' ➡️     Links a Discord user to a WiseOldMan username for mentions when ranking up.",
            "/lookup 'username' ➡️  Lists the rank and EHB for a specific user.",
            "/subscribeall 'discord_name' ➡️    Subscribes a Discord user to ALL usernames.",
            "/unsubscribeall 'discord_name' ➡️  Removes a Discord user from ALL linked usernames.",
            "/commands ➡️   Lists all available commands.",
            "/goodnight ➡️  Sends a good night message.",
            "/forcecheck ➡️     Forces check_for_rank_changes task to run.",
            "/weeklyupdate ➡️   Posts the weekly report to the weekly channel.",
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
            async with aiohttp.ClientSession() as session:
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

    # Command: /link --- Links a Discord user to a WiseOldMan username for mentions when ranking up.

    @bot.tree.command(
        name="link",
        description="Links a Discord user to a WiseOldMan username for mentions when ranking up.",
    )
    @app_commands.describe(username="Wise Old Man username", discord_name="Discord user to link")
    async def link(interaction: Interaction, username: str, discord_name: str):
        try:
            ranks_data = load_ranks()

            if username in ranks_data:
                # Ensure discord_name is stored as a list
                if not isinstance(ranks_data[username].get("discord_name"), list):
                    ranks_data[username]["discord_name"] = [
                        ranks_data[username]["discord_name"]
                    ]
                # Prevent duplicate entries
                if discord_name not in ranks_data[username]["discord_name"]:
                    ranks_data[username]["discord_name"].append(discord_name)
                    save_ranks(ranks_data)
                    await interaction.response.send_message(
                        f"✅ Linked {discord_name} to {username} :)"
                    )
                    if debug:
                        print(f"✅ Linked {discord_name} to {username}.")
                else:
                    await interaction.response.send_message(
                        f"⚠️ {discord_name} is already linked to {username}.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    f"❌ Username '{username}' not found in the ranks data.",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while linking: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /link command: {e}")

    # Command: /unsubscribeall --- Removes a Discord user from all linked usernames in player_ranks.json.

    @bot.tree.command(
        name="unsubscribeall",
        description="Removes a Discord user from all linked usernames.",
    )
    @app_commands.describe(discord_name="Discord user to unsubscribe")
    async def unsubscribeall(interaction: Interaction, discord_name: str):
        try:
            ranks_data = load_ranks()
            removed = False
            count = 0
            if debug:
                print(f"Unsubscribing {discord_name} from all users...")

            # Iterate through all usernames in ranks_data
            for username, data in list(ranks_data.items()):
                if "discord_name" in data and isinstance(data["discord_name"], list):
                    if discord_name in data["discord_name"]:
                        data["discord_name"].remove(discord_name)
                        removed = True
                        count += 1

                        # If the list becomes empty, remove the key entirely
                        if not data["discord_name"]:
                            del data["discord_name"]

            save_ranks(ranks_data)

            if removed:
                await interaction.response.send_message(
                    f"✅ **{discord_name}** has been unsubscribed from **{count}** users."
                )
                if debug:
                    print(f"✅ {discord_name} has been unsubscribed from {count} users.")
            else:
                await interaction.response.send_message(
                    f"⚠️ **{discord_name}** was not found in any subscriptions.",
                    ephemeral=True,
                )
                if debug:
                    print(f"⚠️ {discord_name} was not found in any subscriptions.")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while unsubscribing: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /unsubscribeall command: {e}")

    # Command: /subscribeall --- Subscribes a Discord user to all usernames in player_ranks.json.

    @bot.tree.command(
        name="subscribeall",
        description="Subscribes a Discord user to all usernames in player_ranks.json.",
    )
    @app_commands.describe(discord_name="Discord user to subscribe")
    async def subscribeall(interaction: Interaction, discord_name: str):
        try:
            ranks_data = load_ranks()
            subscribed_count = 0

            # Iterate through all players in ranks_data
            for username, data in ranks_data.items():
                # Ensure discord_name field is initialized as a list
                if "discord_name" not in data or not isinstance(data["discord_name"], list):
                    data["discord_name"] = []
                if discord_name not in data["discord_name"]:
                    data["discord_name"].append(discord_name)
                    subscribed_count += 1

            save_ranks(ranks_data)

            if subscribed_count > 0:
                await interaction.response.send_message(
                    f"✅ **{discord_name}** has been subscribed to **{subscribed_count}** players."
                )
                if debug:
                    print(
                        f"✅ {discord_name} has been subscribed to {subscribed_count} players."
                    )
            else:
                await interaction.response.send_message(
                    f"⚠️ **{discord_name}** is already subscribed to all players.",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while subscribing: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /subscribeall command: {e}")

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

            await interaction.response.send_message(
                f"🔹 **Player:** {username}\n"
                f"🏅 **Current Rank:** {current_rank} ({current_ehb} EHB)\n"
                f"📈 **Next Rank:** {next_rank_info}"
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {e}", ephemeral=True
            )
            if debug:
                print(f"Error in /rankup command: {e}")

