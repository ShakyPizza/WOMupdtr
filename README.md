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
   git clone https://github.com/your-username/WOMupdtr.git
   cd WOMupdtr
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `config.ini` file in the project root directory:
   ```ini
   [discord]
   # Discord bot token
   token = 

   # ID of the Discord channel where rank-up messages will be sent
   channel_id = 

   [wiseoldman]
   # Wise Old Man group ID
   group_id = 
   group_passcode = 

   # Optional: Wise Old Man API key if you have one
   api_key = 

   [settings]
   # Frequency for checking rank updates (in seconds)
   check_interval = 3600

   # Enable/disable initial message on startup
   run_at_startup = false 

   # Enable/disable CSV logging
   PRINT_TO_CSV = false

   # Enable/disable console logging of CSV changes
   print_csv_changes = false

   # Enable/disable Discord notifications
   POST_TO_DISCORD = true

   [Other info]
   # Group passcode for bulk updates
   WOM_group_passcode =

   # Debug mode
   DEBUG = false
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
- The bot automatically tracks ranks based on your configuration
- Use `/refresh` to manually refresh rankings
- Use `/update <username>` to update a specific user's rank information (use quotes for usernames with spaces)

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
