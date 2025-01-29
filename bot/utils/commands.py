from discord.ext import commands
import aiohttp
from rank_utils import load_ranks, save_ranks

def setup_commands(bot, wom_client, GROUP_ID, get_rank, list_all_members_and_ranks, GROUP_PASSCODE):
    
    @bot.command(name="refresh")
    async def refresh(ctx):
        """Refreshes and posts the updated group rankings."""
        try:
            await list_all_members_and_ranks()
            print(f"Refreshed rankings.")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing rankings: {e}")


    @bot.command(name="update")
    async def update(ctx, username: str):
        """Fetches and updates the rank for a specific user by searching the group data."""
        try:
            # Ensure the Wise Old Man client's session is started
            await wom_client.start()

            # Fetch group details
            result = await wom_client.groups.get_details(GROUP_ID)

            if result.is_ok:
                group = result.unwrap()
                # Search for the player in the group memberships
                player = next(
                    (member.player for member in group.memberships if member.player.display_name.lower() == username.lower()),
                    None
                )

                if player:
                    ehb = round(player.ehb, 2)
                    rank = get_rank(ehb)
                    await ctx.send(f"✅ {player.display_name}: {rank} ({ehb} EHB)")
                    print(f"Updated {player.display_name}: {rank} ({ehb} EHB)")
                else:
                    await ctx.send(f"❌ Could not find a player with username '{username}' in the group.")
            else:
                await ctx.send(f"❌ Failed to fetch group details: {result.unwrap_err()}")
        except Exception as e:
            await ctx.send(f"❌ Error updating {username}: {e}")


    @bot.command(name="refreshgroup")
    async def refreshgroup(ctx):
        """Forces a full update for the group's data using the WiseOldMan API."""
        url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}/update-all"
        headers = {"Content-Type": "application/json"}
        payload = {"verificationCode": GROUP_PASSCODE}  # The passcode for the group

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(response.status, data)
                        updated_count = (data.get("count", []))

                        if updated_count > 0:
                            await ctx.send(f"✅ Successfully refreshed group data. {updated_count} members updated. Please allow a few minutes for the changes to reflect.")
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


    @bot.command(name="commands")
    async def commands(ctx):
        """Lists all available commands."""
        command_list = [
            "/refresh - Refreshes and posts the updated group rankings.",
            "/update '""username""' - Fetches and updates the rank for a specific user.",
            "/refreshgroup - Forces a full update for the group's data.",
            "/debug_group - Debugs and inspects group response.",
            "/commands - Lists all available commands.",
            "/goodnight - Sends a good night message."
        ]
        await ctx.send("**Available Commands:**\n" + "\n".join(command_list))

    @bot.command(name="goodnight")
    async def goodnight(ctx):
        await ctx.send("Good night, king 👑")

    @bot.command(name="debug_group")
    async def debug_group(ctx):
        """Debugging command to inspect the group response."""
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

    @bot.command(name="link")
    async def update(ctx, username: str, discord_name: str):
        """Links a discord user to a WiseOldMan username."""
        try:
            ranks_data = load_ranks()
            if username in ranks_data:
                get_rank[username]["discord_name"] = discord_name
                save_ranks(ranks_data)
                await ctx.send(f"✅ Linked {discord_name} to {username}")

        except Exception as e:
            print(f"Error processing player data for {player.username}: {e}")
       


