from discord.ext import commands
import aiohttp

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

    @bot.command(name="refreshwom")
    async def refreshwom(ctx):
        """Updates the group's data using the WiseOldMan API."""
        url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}"
        headers = {"Content-Type": "application/json"}
        payload = {"verificationCode": GROUP_PASSCODE}  # The passcode for the group

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        updated_count = len(data.get("updated", []))

                        if updated_count > 0:
                            await ctx.send(f"✅ Successfully refreshed group data. {updated_count} members updated.")
                            print(f"Group update complete: {updated_count} members updated.")
                        else:
                            await ctx.send("ℹ️ Group is already up to date. No members needed updating.")
                            print("Group is already up to date.")
                    else:
                        error_message = await response.text()
                        await ctx.send(f"❌ Failed to refresh group: {error_message}")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing WiseOldMan group: {e}")
            
        