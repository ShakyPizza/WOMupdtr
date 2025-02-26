#log_csv.py
import csv
from datetime import datetime

def log_ehb_to_csv(username, ehb, file_name="ehb_log.csv", print_csv_changes=True):
    """Logs the username, EHB value, and timestamp to a CSV file."""
    try:
        with open(file_name, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, username, ehb])
            if print_csv_changes:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} - Logged {username} with {ehb} EHB at {timestamp} to {file_name}.")
    except Exception as e:
        print(f"Error logging to CSV: {e}")
