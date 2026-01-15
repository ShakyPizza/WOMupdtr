# WOMupdtr

A Discord bot that integrates with the Wise Old Man API to track, rank, and notify group members based on their EHB (Efficient Hours Bossed). This bot features rank-up notifications, detailed rankings, and CSV logging for group member statistics.

## Features
- **Track Member Rankings**: Automatically fetches and updates group rankings based on EHB.
- **Discord Notifications**: Sends rank-up messages to a specified Discord channel.
- **Commands**:
  - `/refresh`: Refreshes and posts updated rankings.
  - `/update <username>`: Fetches and updates rank information for a specific member.
- **CSV Logging**: Logs EHB values to a CSV file for historical tracking.
- **Automatic Group Refresh**: The clan data is automatically refreshed every `check_interval * 24` seconds.
- **Configurable Settings**: Customize bot behavior through the config file.
- **Baserow Sync**: Optionally update a Baserow database whenever a player's EHB changes.
- **GUI Control Panel**: Manage the bot with a Tkinter interface (`python gui.py`).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ShakyPizza/WOMupdtr.git
   cd WOMupdtr
   ```
2. Install dependencies:
   ```bash
   cd python
   pip install -r requirements.txt
   ```

3. Create a `config.ini` file in the project root directory:
   ```ini
   [discord]
   # Discord bot token
   token = 
   
   # Discord channel ID's ( rich-boys-ranks, rich-boys-stats, osrs-pælingar )
   channel_id          = 
   weekly_channel_id   = 
   monthly_channel_id  = 
   yearly_channel_id   = 
   
   [wiseoldman]
   # Wise Old Man group ID
   group_id = 
   group_passcode =  
   
   # Optional: Wise Old Man API key if you have one.
   api_key = 
   
   [baserow]
   br_token = 
   
   [settings]
   # Frequency for checking rank updates (in seconds)
   check_interval = 3600
   
   # Set to true if you want the bot to send the initial message on startup into the discord channel.
   run_at_startup = false
   
   # Set to true if you want the bot to print the rank changes to ehb_log.csv file.
   print_to_csv = true
   
   # Set to true if you want the .csv changes to be printed in the console.
   print_csv_changes = true
   
   # Set to true if you want the bot to post the rank changes to the discord channel.
   post_to_discord = true
   
   # Silent mode (no console output)
   silent_mode = false
   
   #Debug mode
   debug = true


   


   ```

4. Create a `ranks.ini` file to define rank thresholds:
   ```ini
   [Group Ranking]
   0-10 = Goblin
   10-50 = Opal
   50-120 = Sapphire
   120-250 = Emerald
   250-400 = Red Topaz
   400-550 = Ruby
   550-750 = Diamond
   750-1000 = Dragonstone
   1000-1500 = Onyx
   1500+ = Zenyte
   ```

5. Run the bot from the `python` directory. Use either of the commands below:
   ```bash
   # Headless
   python WOM.py

   # With GUI
   python gui.py
   ```

## Usage

The bot automatically tracks ranks based on your configuration. Below are all available commands:

### General Commands
- `/commands` - Lists all available commands
- `/refresh` - Refreshes and posts the updated group rankings
- `/update <username>` - Fetches and updates the rank for a specific user
- `/lookup <username>` - Lists the rank and EHB for a specific user
- `/rankup <username>` - Displays the current rank, EHB, and next rank for a given player
- `/goodnight` - Sends a good night message

### Group Management
- `/refreshgroup` - Forces a full update for the group's data using the WiseOldMan API
- `/forcecheck` - Forces an immediate check for rank changes
- *Automatic:* This refresh also runs periodically every `check_interval * 48` seconds

### User Linking
- `/link <username> <discord_name>` - Links a Discord user to a WiseOldMan username for rank-up notifications
- `/subscribeall <discord_name>` - Subscribes a Discord user to ALL usernames
- `/unsubscribeall <discord_name>` - Removes a Discord user from ALL linked usernames

### Debug Commands
- `/debug_group` - Debugs and inspects group response
- `/sendrankup_debug` - Debugging command to simulate a rank up message

**Note**: For usernames with spaces, enclose them in quotes (e.g., "/update 'Player Name'")

## Logging
- EHB values are logged to `python/ehb_log.csv` by default (the path is resolved relative to the `python` folder so you can run the bot from anywhere).
- Configure logging behavior in `config.ini`:
  - `PRINT_TO_CSV`: Enable/disable CSV logging
  - `print_csv_changes`: Enable/disable console logging of CSV updates

## Running Tests
Run the unit tests with:
```bash
pytest
```

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Submit a pull request

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgments
- [Wise Old Man API](https://wiseoldman.net/) for OSRS player data
- [Discord.py](https://discordpy.readthedocs.io/) for Discord integration

Happy Bossing!
