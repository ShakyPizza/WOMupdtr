from discord.ext import commands
import aiohttp
from datetime import datetime
from .rank_utils import load_ranks, save_ranks, next_rank


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def format_discord_fans(discord_fans):
    """
    Formats the Discord fans for display.
    
    If discord_fans is a list, join its items with " + ". Otherwise, return the string.
    If no fans exist, return "0 😭".
    """
    if isinstance(discord_fans, list):
        return " + ".join(discord_fans) if discord_fans else "0 😭"
    return discord_fans if discord_fans else "0 😭"


# ------------------------------------------------------------------------------
# Setup Commands Function
# ------------------------------------------------------------------------------
def setup_commands(
    bot, wom_client, GROUP_ID, get_rank, list_all_members_and_ranks, GROUP_PASSCODE, send_rank_up_message, check_for_rank_changes, debug
):

    # ------------------------------------------------------------------------------
    # Command: /lookup --- Lists the rank and EHB for a specific user.
    # ------------------------------------------------------------------------------
    @bot.command(name="lookup")
    async def lookup(ctx, username: str):
        try:
            ranks_data = load_ranks()

            if username in ranks_data:
                ehb = ranks_data[username]["last_ehb"]
                rank = ranks_data[username]["rank"]
                discord_fans = ranks_data[username]["discord_name"]
                fans_display = format_discord_fans(discord_fans)

                await ctx.send(
                    f"**{username}**\n**Rank:** {rank} ({ehb} EHB)\n**Fans:** {fans_display}"
                )
                print(f"Listed {username}: {rank} ({ehb} EHB), Fans: {fans_display}")
            else:
                await ctx.send(f"❌ Username **'{username}'** not found in the ranks data.")
                print(f"Username **{username}** not found in the ranks data.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred while linking: {e}")
            print(f"Error in /lookup command: {e}")

    # ------------------------------------------------------------------------------
    # Command: /refresh --- Refreshes and posts the updated group rankings.
    # ------------------------------------------------------------------------------
    @bot.command(name="refresh")
    async def refresh(ctx):
        try:
            await list_all_members_and_ranks()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{timestamp} - Refreshed rankings via Discord Command.")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing rankings: {e}")

    # ------------------------------------------------------------------------------
    # Command: /forcecheck --- Forces check_for_rank_changes to run.
    # ------------------------------------------------------------------------------
    @bot.command(name="forcecheck")
    async def forcecheck(ctx):
        try:
            await check_for_rank_changes()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{timestamp} - Forced check_for_rank function.")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing rankings: {e}")

    # ------------------------------------------------------------------------------
    # Command: /update --- Fetches and updates the rank for a specific user by searching the group data.
    # ------------------------------------------------------------------------------
    @bot.command(name="update")
    async def update(ctx, username: str):
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
                    await ctx.send(
                        f"✅ **{player.display_name}** \n**Rank:** {rank} ({ehb} EHB)\n**Fans:** {fans_display}"
                    )
                    print(f"Updated {player.display_name}: {rank} ({ehb} EHB), Fans: {fans_display}")
                else:
                    await ctx.send(f"❌ Could not find a player with username **{username}** in the group.")
            else:
                await ctx.send(f"❌ Failed to fetch group details: {result.unwrap_err()}")
        except Exception as e:
            await ctx.send(f"❌ Error updating {username}: {e}")
            print(f"Error in /update command: {e}")

    # ------------------------------------------------------------------------------
    # Command: /refreshgroup --- Forces a full update for the group's data using the WiseOldMan API.
    # ------------------------------------------------------------------------------
    @bot.command(name="refreshgroup")
    async def refreshgroup(ctx):
        url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}/update-all"
        headers = {"Content-Type": "application/json"}
        payload = {"verificationCode": GROUP_PASSCODE}  # The passcode for the group

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(response.status, data)
                        updated_count = data.get("count", 0)

                        if updated_count > 0:
                            await ctx.send(
                                f"✅ Successfully refreshed group data. **{updated_count}** members updated. Please allow a few minutes for the changes to reflect."
                            )
                            print(f"Group update complete: {updated_count} members updated.")
                        else:
                            await ctx.send("ℹ️ Group data is already up to date. No members required updating.")
                            print("Group data is already up to date.")
                    elif response.status == 400:
                        error_message = await response.json()
                        if error_message.get("message") == "Nothing to update.":
                            await ctx.send("ℹ️ The API reported 'Nothing to update'. The group data is already current.")
                            print("The API reported 'Nothing to update'.")
                        else:
                            await ctx.send(f"❌ Failed to refresh group: {error_message}")
                    else:
                        error_message = await response.text()
                        await ctx.send(f"❌ Failed to refresh group: {error_message}")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing WiseOldMan group: {e}")

    # ------------------------------------------------------------------------------
    # Command: /commands --- Lists all available commands.
    # ------------------------------------------------------------------------------
    @bot.command(name="commands")
    async def commands_list(ctx):
        command_list = [
            "**Usernames with spaces in them need to be enclosed in quotes.**",
            "Usernames are case-sensitive except for **/update** command",
            "/refresh ➡️ Refreshes and posts the updated group rankings.",
            "/update 'username' ➡️ Fetches and updates the rank for a specific user.",
            "/rankup 'username' ➡️ Displays the current rank, EHB, and next rank for a given player.",
            "/refreshgroup ➡️ Forces a full update for the group's data.",
            "/link 'username' 'discord_name' ➡️ Links a Discord user to a WiseOldMan username for mentions when ranking up.",
            "/lookup 'username' ➡️ Lists the rank and EHB for a specific user.",
            "/subscribeall 'discord_name' ➡️ Subscribes a Discord user to ALL usernames.",
            "/unsubscribeall 'discord_name' ➡️ Removes a Discord user from ALL linked usernames.",
            "/commands ➡️ Lists all available commands.",
            "/goodnight ➡️ Sends a good night message.",
            "/forcecheck ➡️ Forces check_for_rank_changes task to run.",
            "/sendrankup_debug ➡️ Debugging command to simulate a rank up message.",
            "/debug_group ➡️ Debugs and inspects group response.",
        ]
        await ctx.send("**Available Commands:**\n" + "\n".join(command_list))

    # ------------------------------------------------------------------------------
    # Command: /goodnight --- Sends a good night message.
    # ------------------------------------------------------------------------------
    @bot.command(name="goodnight")
    async def goodnight(ctx):
        await ctx.send("Good night, king 👑")

    # ------------------------------------------------------------------------------
    # Command: /debug_group --- Debugging command to inspect the group response.
    # ------------------------------------------------------------------------------
    @bot.command(name="debug_group")
    async def debug_group(ctx):
        url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        group_data = await response.json()
                        group_name = group_data.get("name", "Unknown")
                        member_count = len(group_data.get("memberships", []))
                        await ctx.send(f"Group Name: {group_name}\nMembers: {member_count}")
                        # Log the full group data for manual inspection
                        print(group_data)
                    else:
                        error_message = await response.text()
                        await ctx.send(f"Failed to fetch group details: {error_message}")
        except Exception as e:
            await ctx.send(f"Error fetching group details: {e}")

    # ------------------------------------------------------------------------------
    # Command: /link --- Links a Discord user to a WiseOldMan username for mentions when ranking up.
    # ------------------------------------------------------------------------------
    @bot.command(name="link")
    async def link(ctx, username: str, discord_name: str):
        try:
            ranks_data = load_ranks()

            if username in ranks_data:
                # Ensure discord_name is stored as a list
                if not isinstance(ranks_data[username].get("discord_name"), list):
                    ranks_data[username]["discord_name"] = [ranks_data[username]["discord_name"]]
                # Prevent duplicate entries
                if discord_name not in ranks_data[username]["discord_name"]:
                    ranks_data[username]["discord_name"].append(discord_name)
                    save_ranks(ranks_data)
                    await ctx.send(f"✅ Linked {discord_name} to {username} :)")
                    print(f"✅ Linked {discord_name} to {username}.")
                else:
                    await ctx.send(f"⚠️ {discord_name} is already linked to {username}.")
            else:
                await ctx.send(f"❌ Username '{username}' not found in the ranks data.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred while linking: {e}")
            print(f"Error in /link command: {e}")

    # ------------------------------------------------------------------------------
    # Command: /unsubscribeall --- Removes a Discord user from all linked usernames in player_ranks.json.
    # ------------------------------------------------------------------------------
    @bot.command(name="unsubscribeall")
    async def unsubscribeall(ctx, discord_name: str):
        try:
            ranks_data = load_ranks()
            removed = False
            count = 0
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
                await ctx.send(f"✅ **{discord_name}** has been unsubscribed from **{count}** users.")
                print(f"✅ {discord_name} has been unsubscribed from {count} users.")
            else:
                await ctx.send(f"⚠️ **{discord_name}** was not found in any subscriptions.")
                print(f"⚠️ {discord_name} was not found in any subscriptions.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred while unsubscribing: {e}")
            print(f"Error in /unsubscribeall command: {e}")

    # ------------------------------------------------------------------------------
    # Command: /subscribeall --- Subscribes a Discord user to all usernames in player_ranks.json.
    # ------------------------------------------------------------------------------
    @bot.command(name="subscribeall")
    async def subscribeall(ctx, discord_name: str):
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
                await ctx.send(f"✅ **{discord_name}** has been subscribed to **{subscribed_count}** players.")
                print(f"✅ {discord_name} has been subscribed to {subscribed_count} players.")
            else:
                await ctx.send(f"⚠️ **{discord_name}** is already subscribed to all players.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred while subscribing: {e}")
            print(f"Error in /subscribeall command: {e}")

    # ------------------------------------------------------------------------------
    # Command: /sendrankup_debug --- Debugging command to simulate a rank up message.
    # ------------------------------------------------------------------------------
    @bot.command(name="sendrankup_debug")
    async def sendrankup_debug(ctx):
        try:
            # Using fixed test values for debugging
            test_username = "Zezima"
            new_rank = "Legend"
            old_rank = "Hero"
            ehb = 1000000000
            await send_rank_up_message(test_username, new_rank, old_rank, ehb)
            print("✅ Successfully sent a rank up message to the channel.")
        except Exception as e:
            await ctx.send(f"❌ Error sending a rank up message to the channel: {e}")

    # ------------------------------------------------------------------------------
    # Command: /rankup --- Displays the current rank, EHB, and next rank for a given player.
    # ------------------------------------------------------------------------------
    @bot.command(name="rankup")
    async def rankup(ctx, username: str):
        try:
            ranks_data = load_ranks()
            if username not in ranks_data:
                await ctx.send(f"❌ Username '{username}' not found in the ranks data.")
                return

            user_data = ranks_data[username]
            current_rank = user_data.get("rank", "Unknown")
            current_ehb = user_data.get("last_ehb", 0)
            next_rank_info = next_rank(username)

            await ctx.send(
                f"🔹 **Player:** {username}\n"
                f"🏅 **Current Rank:** {current_rank} ({current_ehb} EHB)\n"
                f"📈 **Next Rank:** {next_rank_info}"
            )
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}")
            print(f"Error in /rankup command: {e}")