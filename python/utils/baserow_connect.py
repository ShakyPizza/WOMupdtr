# baserow_connect.py
import requests

from .config_loader import get_config_value, load_config


config = load_config()
token = get_config_value(
    "baserow", "token", "BASEROW_TOKEN", config, required=False, default=""
)

def post_to_ehb_table(username, date, ehb):
    #Create a row in the players table (id 613979).

    if not token:
        raise ValueError("Baserow token is not set. Set BASEROW_TOKEN or update config.ini.")

    post = requests.post(
        "https://api.baserow.io/api/database/rows/table/613979/?user_field_names=true",
        headers={
            "Authorization": "Token {token}".format(token=token),
            "Content-Type": "application/json",
        },
        json={
            "Username": username,
            "Date": date,
            "EHB": ehb,
        },
    )

    if post.status_code != 200:
        print("Error: ", post.status_code)


def update_players_table(username, rank, ehb, discord_names=None):
    #Create or update a row in the players table (id 613980)

    

    if not token:
        raise ValueError("Baserow token is not set. Set BASEROW_TOKEN or update config.ini.")

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
                json={"Username": username, "Rank": rank, "last_ehb": ehb, "discord_name": discord_value},
            )
            print(f"Updating player {username} with rank {rank}, EHB {ehb}, and Discord names {discord_names} in Baserow Player Table")
            if patch.status_code != 200:
                print("Error updating player row: ", patch.status_code)
        else:
            post = requests.post(
                f"{base_url}?user_field_names=true",
                headers=headers,
                json={"Username": username, "Rank": rank, "last_ehb": ehb, "discord_name": discord_value},
            )
            print(f"Creating player {username} with rank {rank}, EHB {ehb}, and Discord names {discord_names} in Baserow Player Table")
            if post.status_code != 200:
                print("Error creating player row: ", post.status_code)
    else:
        print("Error fetching player row: ", get.status_code)
