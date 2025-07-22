#baserow_connect.py
import configparser
import requests
import os
from datetime import datetime

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
config.read(config_file)
token = config.get('baserow', 'token', fallback='')

if not token:
    raise ValueError("Baserow token is not set in the config.ini file.")

def post_to_ehb_table(username, date, ehb):
    #Create a row in the players table (id 613979).

    post = requests.post(
            "https://api.baserow.io/api/database/rows/table/613979/?user_field_names=true",
            headers={
                "Authorization": "Token {token}".format(token=token),
                "Content-Type": "application/json"
            },
            json={
                "Username": username,
                "Date": date,
                "EHB": ehb
            }
        )

    if post.status_code != 200:
        print("Error: ", post.status_code)


def update_players_table(username, rank, ehb, discord_names=None):
    #Create or update a row in the players table (id 613980)

    print(f"Updating player {username} with rank {rank}, EHB {ehb}, and Discord names {discord_names} in Baserow Player Table")

    base_url = "https://api.baserow.io/api/database/rows/table/613980/"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    # Convert list of discord names to comma separated string if provided
    if isinstance(discord_names, list):
        discord_value = ", ".join(discord_names)
    else:
        discord_value = discord_names or ""

    # Check if the player already exists
    get = requests.get(
        f"{base_url}?user_field_names=true&filter__Username__equal={username}",
        headers=headers,
    )

    if get.status_code == 200:
        data = get.json()
        if data.get("results"):
            row_id = data["results"][0]["id"]
            patch = requests.patch(
                f"{base_url}{row_id}/?user_field_names=true",
                headers=headers,
                json={"Username": username, "Rank": rank, "EHB": ehb, "Discord": discord_value},
            )
            if patch.status_code != 200:
                print("Error updating player row: ", patch.status_code)
        else:
            post = requests.post(
                f"{base_url}?user_field_names=true",
                headers=headers,
                json={"Username": username, "Rank": rank, "EHB": ehb, "Discord": discord_value},
            )
            if post.status_code != 200:
                print("Error creating player row: ", post.status_code)
    else:
        print("Error fetching player row: ", get.status_code)
