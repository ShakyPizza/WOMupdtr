import configparser
from wom import Client
from discord.ext import tasks
import discord
from datetime import datetime
import asyncio

RANK_ICONS = {
    "Recruit": "https://oldschool.runescape.wiki/images/recruit_icon.png",
    "Corporal": "https://oldschool.runescape.wiki/images/corporal_icon.png",
    "Sergeant": "https://oldschool.runescape.wiki/images/sergeant_icon.png",
    "Lieutenant": "https://oldschool.runescape.wiki/images/lieutenant_icon.png",
    "Captain": "https://oldschool.runescape.wiki/images/captain_icon.png",
    "General": "https://oldschool.runescape.wiki/images/general_icon.png",
    "Admin": "https://oldschool.runescape.wiki/images/admin_icon.png",
    "Organiser": "https://oldschool.runescape.wiki/images/organiser_icon.png",
    "Coordinator": "https://oldschool.runescape.wiki/images/coordinator_icon.png",
    "Overseer": "https://oldschool.runescape.wiki/images/overseer_icon.png",
    "Deputy Owner": "https://oldschool.runescape.wiki/images/deputy_owner_icon.png",
    "Owner": "https://oldschool.runescape.wiki/images/owner_icon.png",
}


# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Discord and Wise Old Man settings
DISCORD_TOKEN = config['discord']['token']
CHANNEL_ID = int(config['discord']['channel_id'])
GROUP_ID = int(config['wiseoldman']['group_id'])
CHECK_INTERVAL = int(config['settings']['check_interval'])  # Check interval in seconds, directly from config

# Initialize Wise Old Man client
wom_client = Client()

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
discord_client = discord.Client(intents=intents)

# Dictionary to store previous EHB values
previous_ehb = {}

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')

    # Start the Wise Old Man client session
    await wom_client.start()

    # Call the one-time member and ranks listing function
    await list_all_members_and_ranks()

    # Start rank checking task if not already running
    if not check_for_rank_changes.is_running():
        print("Starting check_for_rank_changes task.")
        check_for_rank_changes.start()
    else:
        print("check_for_rank_changes task is already running.")




def get_rank(ehb, ranks_file='ranks.ini'):
    try:
        config = configparser.ConfigParser()
        config.read(ranks_file)

        # Parse ranks from the INI file
        for range_key, rank_name in config['Rich Boys Ranking'].items():
            if '+' in range_key:  # Handle ranges like '1500+'
                lower_bound = int(range_key.replace('+', ''))
                if ehb >= lower_bound:
                    return rank_name
            else:
                # Handle ranges like '0-10'
                lower_bound, upper_bound = map(int, range_key.split('-'))
                if lower_bound <= ehb < upper_bound:
                    return rank_name
    except Exception as e:
        print(f"Error reading ranks.ini: {e}")
    return "Unknown"  # Default if no rank matches


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_for_rank_changes():
    try:
        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships

            for membership in memberships:
                try:
                    player = membership.player

                    username = player.display_name
                    ehb = round(player.ehb, 2)  # Rounded to 2 decimals
                    rank = get_rank(ehb)  # Determine rank

                    print(f"Processing {username}: Current EHB = {ehb}, Rank = {rank}")

                    # Compare and notify if rank increases
                    if username in previous_ehb and ehb > previous_ehb[username]:
                        await send_rank_up_message(username, f"{rank} ({ehb} EHB)")

                    # Update stored EHB values
                    previous_ehb[username] = ehb

                except Exception as e:
                    print(f"Error processing player data for {player.username}: {e}")
        else:
            print(f"Failed to fetch group details: {result.unwrap_err()}")

    except Exception as e:
        print(f"Error occurred during rank check: {e}")

async def list_all_members_and_ranks():
    try:
        # Ensure the Wise Old Man client's HTTP session is started
        await wom_client.start()

        # Fetch group details
        result = await wom_client.groups.get_details(GROUP_ID)

        if result.is_ok:
            group = result.unwrap()
            memberships = group.memberships

            # Prepare the message header
            message_lines = ["**Rich Boys Ranking**\n"]
            message_lines.append("```")
            message_lines.append(f"{'Player':<20}{'Rank':<15}{'EHB':<10}")
            message_lines.append(f"{'-'*45}")

            for membership in memberships:
                try:
                    player = membership.player

                    username = player.display_name
                    ehb = round(player.ehb, 2)  # Rounded to 2 decimals
                    rank = get_rank(ehb)  # Determine rank from the ranks.ini file

                    # Add member's rank to the message with proper alignment
                    message_lines.append(f"{username:<20}{rank:<15}{ehb:<10}")
                except Exception as e:
                    print(f"Error processing player data for {membership.player.username}: {e}")

            message_lines.append("```")  # End code block

            # Join all message lines
            final_message = "\n".join(message_lines)

            # Check and send the message to the Discord channel
            channel = discord_client.get_channel(CHANNEL_ID)
            if channel:
                print(f"Sending message to channel: {channel.name}")
                await channel.send(final_message)  # Send the message
            else:
                print(f"Channel with ID {CHANNEL_ID} not found.")
        else:
            print(f"Failed to fetch group details: {result.unwrap_err()}")
    except Exception as e:
        print(f"Error occurred while listing members and ranks: {e}")


async def send_rank_up_message(username, rank, ehb):
    try:
        channel = discord_client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f'🎉 Congratulations {username} on achieving the rank of {rank} with {ehb} EHB! 🎉')
        else:
            print(f"Channel with ID {CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error sending message: {e}")


# Run the Discord bot
discord_client.run(DISCORD_TOKEN)
