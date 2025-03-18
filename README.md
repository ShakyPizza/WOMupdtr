# WOMupdtr

A Discord bot that integrates with the Wise Old Man API to track, rank, and notify group members based on their EHB (Efficient Hours Bossed). This bot features rank-up notifications, detailed rankings, and CSV logging for group member statistics.

## Features
- **Track Member Rankings**: Automatically fetches and updates group rankings based on EHB.
- **Discord Notifications**: Sends rank-up messages to a specified Discord channel.
- **Commands**:
  - `/refresh`: Refreshes and posts updated rankings.
  - `/update <username>`: Fetches and updates rank information for a specific member.
- **CSV Logging**: Logs EHB values to a CSV file for historical tracking.
- **Configurable Settings**: Customize bot behavior through the config file.

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
   token =
   channel_id =

   [wiseoldman]
   group_id =
   group_passcode =
   api_key =

   [settings]
   check_interval = 3600
   run_at_startup = false
   print_to_csv = true
   print_csv_changes = false
   post_to_discord = false
   debug = false
   silent = false

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

5. Run the bot:
   ```bash
   python WOM.py
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

### User Linking
- `/link <username> <discord_name>` - Links a Discord user to a WiseOldMan username for rank-up notifications
- `/subscribeall <discord_name>` - Subscribes a Discord user to ALL usernames
- `/unsubscribeall <discord_name>` - Removes a Discord user from ALL linked usernames

### Debug Commands
- `/debug_group` - Debugs and inspects group response
- `/sendrankup_debug` - Debugging command to simulate a rank up message

**Note**: For usernames with spaces, enclose them in quotes (e.g., "/update 'Player Name'")

## Logging
- EHB values are logged to `ehb_log.csv`
- Configure logging behavior in `config.ini`:
  - `PRINT_TO_CSV`: Enable/disable CSV logging
  - `print_csv_changes`: Enable/disable console logging of CSV updates

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
