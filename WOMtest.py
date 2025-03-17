WOMtest.py

# A test script to gather data from the Wise Old Man API

import requests

# Define the API endpoint
url = "https://api.wiseoldman.net/v1/groups/1234567890"

# Send a GET request to the API endpoint
response = requests.get(url)


