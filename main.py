import discord
from discord.ext import tasks
from wom import Client

# Initialize Wise Old Man and Discord clients
wom_client = Client()
discord_client = discord.Client()

# Your Discord bot token
DISCORD_TOKEN = 'your_discord_bot_token'
# Your Discord channel ID for rank-up notifications
CHANNEL_ID = your_channel_id
# Wise Old Man group ID
GROUP_ID = 2300

# Dictionary to store previous EHB values
previous_ehb = {}

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')
    check_for_rank_changes.start()

@tasks.loop(hours=1)  # Adjust the interval as needed
async def check_for_rank_changes():
    group = wom_client.groups.get_group(GROUP_ID)
    members = group.members

    for member in members:
        player = wom_client.players.get_player(member.username)
        ehb = player.ehb

        if member.username in previous_ehb:
            if ehb > previous_ehb[member.username]:
                await send_rank_up_message(member.username, ehb)

        previous_ehb[member.username] = ehb

async def send_rank_up_message(username, ehb):
    channel = discord_client.get_channel(CHANNEL_ID)
    await channel.send(f'Congratulations {username} on achieving {ehb} EHB!')

discord_client.run(DISCORD_TOKEN)
