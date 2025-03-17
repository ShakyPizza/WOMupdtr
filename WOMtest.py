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

def setup_logging():
    """Sets up logging to both file and console"""
    log_file = open("log.txt", "w")
    
    class TeeOutput:
        def __init__(self, filename, original_stdout):
            self.terminal = original_stdout
            self.log_file = open(filename, "w")
        
        def write(self, message):
            self.terminal.write(message)
            self.log_file.write(message)
        
        def flush(self):
            self.terminal.flush()
            self.log_file.flush()
        
        def close(self):
            self.log_file.close()
    
    sys.stdout = TeeOutput("log.txt", sys.stdout)

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
    # Setup logging
    setup_logging()
    
    # Start the WOM client session
    await wom_client.start()
    log("WOM client started")
    
    # Fetch group details
    result = await wom_client.groups.get_details(group_id)
    log("Group details fetched successfully")
    print("\nGroup details:")
    print(result)
    
    # Close the client session when done
    await wom_client.close()
    log("WOM client closed")
    
    # Restore original stdout and close log file
    sys.stdout.close()
    sys.stdout = sys.__stdout__

asyncio.run(main())











