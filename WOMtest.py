# WOMtest.py
# A test script to gather data from the Wise Old Man API

from wom import Client
import configparser
import os
from datetime import datetime
import asyncio
from discord.ext import tasks
import sys
# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

old_stdout = sys.stdout
log_file = open("log.txt", "w")
sys.stdout = log_file


def log(message: str):
    """Logs a message with the current timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{timestamp} - {message}"
    print(formatted_message)  # Print to terminal

# ------------------------------------------------------------------------------
# Configuration Loading
# ------------------------------------------------------------------------------

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_file)


# Fetch settings from config.ini	

channel_id          = int(config['discord']['channel_id'])
group_id            = int(config['wiseoldman']['group_id'])
group_passcode      = config['wiseoldman']['group_passcode']

# ------------------------------------------------------------------------------
# Wise Old Man Client Initialization
# ------------------------------------------------------------------------------

wom_client = Client()


async def main():
    # Start the WOM client session
    await wom_client.start()
    
    # Fetch group details
    result = await wom_client.groups.get_details(group_id)
    sys.stdout = old_stdout
    log_file.close()
    print("Group details fetched successfully")
    
    # Close the client session when done
    await wom_client.close()

asyncio.run(main())











