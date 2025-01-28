from discord.ext import commands

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
