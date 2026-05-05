import json
import os
import configparser
from .database import upsert_players
from .log_csv import load_latest_ehb_from_csv

# JSON file for storing player ranks
RANKS_FILE = os.path.join(os.path.dirname(__file__), 'player_ranks.json')
_BOOTSTRAPPED_FROM_CSV = False


def _get_rank_for_ehb(ehb):
    """Return rank name for an EHB value using ranks.ini thresholds."""
    ranks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ranks.ini')
    try:
        rank_config = configparser.ConfigParser()
        rank_config.read(ranks_path)
        for range_key, rank_name in rank_config['Group Ranking'].items():
            if '+' in range_key:
                lower_bound = int(range_key.replace('+', ''))
                if ehb >= lower_bound:
                    return rank_name
            else:
                lower_bound, upper_bound = map(int, range_key.split('-'))
                if lower_bound <= ehb < upper_bound:
                    return rank_name
    except Exception as e:
        print(f"Error reading ranks.ini for CSV bootstrap: {e}")
    return "Unknown"


def _bootstrap_ranks_from_csv():
    """Seed ranks data from ehb_log.csv when JSON storage is missing/corrupt."""
    global _BOOTSTRAPPED_FROM_CSV
    ehb_map = load_latest_ehb_from_csv()
    if not ehb_map:
        return {}
    _BOOTSTRAPPED_FROM_CSV = True
    ranks_data = {}
    for username, ehb in ehb_map.items():
        ranks_data[username] = {
            "last_ehb": ehb,
            "rank": _get_rank_for_ehb(ehb),
        }
    print("Loaded ranks from ehb_log.csv.")
    return ranks_data

def load_ranks():
    """Load ranks from a JSON file."""
    if os.path.exists(RANKS_FILE):
        try:
            with open(RANKS_FILE, 'r') as f:
                return json.load(f)

        except (json.JSONDecodeError, ValueError):
            print(f"Error: {RANKS_FILE} is empty or corrupted. Resetting data.")
            return _bootstrap_ranks_from_csv()
    return _bootstrap_ranks_from_csv()

def save_ranks(data):
    """Save ranks to ``player_ranks.json`` and sync the latest snapshot to SQLite."""
    sanitized_data = {
        username: {
            "last_ehb": pdata.get("last_ehb", 0),
            "rank": pdata.get("rank", "Unknown"),
        }
        for username, pdata in data.items()
    }

    # Load existing data to compare EHB values
    old_data = {}
    if os.path.exists(RANKS_FILE):
        try:
            with open(RANKS_FILE, "r") as f:
                old_data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            old_data = {}

    # Write the new data to disk
    with open(RANKS_FILE, "w") as f:
        json.dump(sanitized_data, f, indent=4)

    try:
        changed_rows = {
            username: pdata
            for username, pdata in sanitized_data.items()
            if old_data.get(username, {}).get("last_ehb") != pdata.get("last_ehb")
            or old_data.get(username, {}).get("rank") != pdata.get("rank")
        }
        if changed_rows:
            upsert_players(changed_rows)
    except Exception as e:
        print(f"Error updating SQLite player snapshot: {e}")

def next_rank(username):
    """Returns the next rank for a given player based on their current EHB."""
    try:
        ranks_data = load_ranks()
        user_data = ranks_data.get(username)

        if not user_data:
            return "Unknown"  # Return 'Unknown' if the user is not found

        current_ehb = user_data.get("last_ehb", 0)
        current_rank = user_data.get("rank", "Unknown")

        # Load rank thresholds from ranks.ini
        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ranks.ini'))

        rank_thresholds = []
        for range_key, rank_name in config['Group Ranking'].items():
            if '+' in range_key:  # Handle "1500+" case
                lower_bound = int(range_key.replace('+', ''))
                rank_thresholds.append((lower_bound, rank_name))
            else:
                lower_bound, upper_bound = map(int, range_key.split('-'))
                rank_thresholds.append((lower_bound, rank_name))

        # Sort by EHB threshold
        rank_thresholds.sort()

        # Find the next rank
        for i, (ehb_threshold, rank_name) in enumerate(rank_thresholds):
            if current_rank == rank_name and i + 1 < len(rank_thresholds):
                next_rank_name = rank_thresholds[i + 1][1]
                next_ehb_threshold = rank_thresholds[i + 1][0]
                return  f"{next_rank_name} at {next_ehb_threshold} EHB"
        
        return "Max Rank Achieved 👑"  # If they are at the highest rank

    except Exception as e:
        print(f"Error in next_rank function: {e}")
        return "Error fetching next rank"
