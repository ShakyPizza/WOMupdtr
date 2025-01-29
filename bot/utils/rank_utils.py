import json
import os

# JSON file for storing player ranks
RANKS_FILE = os.path.join(os.path.dirname(__file__), 'player_ranks.json')

def load_ranks():
    """Load ranks from a JSON file and ensure discord_name is always a list."""
    if os.path.exists(RANKS_FILE):
        try:
            with open(RANKS_FILE, 'r') as f:
                ranks_data = json.load(f)

            # Ensure discord_name is always a list
            for username, data in ranks_data.items():
                if "discord_name" not in data:
                    data["discord_name"] = []  # Initialize missing field as a list
                elif isinstance(data["discord_name"], str):
                    data["discord_name"] = [data["discord_name"]]  # Convert string to list

            return ranks_data

        except (json.JSONDecodeError, ValueError):
            print(f"Error: {RANKS_FILE} is empty or corrupted. Resetting data.")
            return {}
    return {}

def save_ranks(data):
    """Save ranks to a JSON file."""
    with open(RANKS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
