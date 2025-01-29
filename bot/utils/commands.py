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
        """Forces updates for all members in the group using the WiseOldMan API."""
        group_url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}"
        player_update_url = "https://api.wiseoldman.net/v2/players/track"
        headers = {"Content-Type": "application/json"}
        payload = {"verificationCode": GROUP_PASSCODE}  # The group passcode

        try:
            async with aiohttp.ClientSession() as session:
                # Fetch group details to get the members
                async with session.get(group_url) as response:
                    if response.status == 200:
                        group_data = await response.json()
                        members = group_data.get("members", [])
                        if not members:
                            await ctx.send("❌ No members found in the group.")
                            return
                        
                        # Update each member individually
                        updated_count = 0
                        for member in members:
                            member_name = member.get("displayName")
                            if not member_name:
                                continue
                            player_payload = {"username": member_name}
                            async with session.post(player_update_url, headers=headers, json=player_payload) as player_response:
                                if player_response.status == 200:
                                    updated_count += 1
                        
                        await ctx.send(f"✅ Successfully refreshed {updated_count} members.")
                    else:
                        error_message = await response.text()
                        await ctx.send(f"❌ Failed to fetch group details: {error_message}")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing WiseOldMan group: {e}")
            