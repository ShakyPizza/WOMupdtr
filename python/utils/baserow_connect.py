#baserow_connect.py
import configparser
import requests
import os
from datetime import datetime

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
config.read(config_file)
token = str(config['baserow']['token'])

if not token:
    raise ValueError("Baserow token is not set in the config.ini file.")

def post_to_ehb_table(username, date, ehb):
    
    post = requests.post(
            "https://api.baserow.io/api/database/rows/table/613979/?user_field_names=true",
            headers={
                "Authorization": "Token {token}".format(token=token),
                "Content-Type": "application/json"
            },
            json={
                "Username": {username},
                "Date": {date},
                "EHB": {ehb}
            }
        )

    if post.status_code != 200:
        print("Error: ", post.status_code)
    else:
        print("Success posting to EHB table: ", post.status_code)

post_to_ehb_table()
