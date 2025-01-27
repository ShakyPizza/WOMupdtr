# WOMupdtr
# Rich Boys Ranking Bot

A Discord bot that integrates with the Wise Old Man API to track, rank, and notify group members based on their EHB (Efficient Hours Bossed). This bot features rank-up notifications, detailed rankings, and CSV logging for group member statistics.

## Features
- **Track Member Rankings**: Automatically fetches and updates group rankings based on EHB.
- **Discord Notifications**: Sends rank-up messages to a specified Discord channel.
- **Commands**:
  - `/refresh`: Refreshes and posts updated rankings.
  - `/update <username>`: Fetches and updates rank information for a specific member.
- **CSV Logging**: Logs EHB values to a CSV file for historical tracking.
- **Configurable Settings**:
  - Enable or disable logging and rank messages at startup.
  - Customize check intervals and rank ranges via configuration files.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/rich-boys-ranking-bot.git
   cd rich-boys-ranking-bot
   ```

2. Install dependencies for WOMupdtr bot:
   ```bash
   pip install -r bot_reqs.txt
   ```

3. Create a `config.ini` file in the project root directory:
   ```ini
   [discord]
   token = your-discord-bot-token
   channel_id = your-channel-id

   [wiseoldman]
   group_id = your-group-id

   [settings]
   check_interval = 3600  # Interval in seconds for rank checking
   run_at_startup = true  # Set to true to post rankings on startup
   print_csv_changes = true  # Set to false to disable terminal logging of CSV updates
   ```

4. Create a `ranks.ini` file to define rank thresholds, example shown here:
   ```ini
   [Rich Boys Ranking]
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
- The bot will automatically start tracking ranks based on your configuration.
- Use the `/refresh` command to manually refresh rankings.
- Use the `/update <username>` command to get updated rank information for a specific user, if username has spaces use "<username>".

## Logging
- EHB values are logged to `ehb_log.csv` for tracking purposes.
- Logging to CSV can be toggled with via `print_to_csv` setting in `config.ini`.
- Terminal logging of CSV updates can be toggled via the `print_csv_changes` setting in `config.ini`.

## Development

To contribute to this project:
1. Fork the repository.
2. Create a new feature branch.
3. Commit your changes and push to your fork.
4. Submit a pull request.

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgments
- [Wise Old Man API](https://wiseoldman.net/) for providing player data.
- [Discord.py](https://discordpy.readthedocs.io/) for enabling Discord bot functionality.

---

## Requirements

### Plugin Requirements (`plugin_reqs.txt`)
- Java 11+
- Gradle 8.12+
- Runelite API dependencies (documented in `build.gradle`)

### Bot Requirements (`bot_reqs.txt`)
Install Python dependencies using:
```bash
pip install -r bot_reqs.txt


---

### 5. **Install the Requirements**
To install the dependencies:
- For the bot:
  ```bash
  pip install -r bot_reqs.txt


Happy Bossing!
