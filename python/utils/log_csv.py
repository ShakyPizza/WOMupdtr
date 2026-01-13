#log_csv.py
import csv
import os
from datetime import datetime


def _resolve_csv_path(file_name: str) -> str:
    """Return an absolute, writable-friendly path for the CSV log."""
    env_path = os.environ.get("EHB_LOG_PATH")
    if env_path:
        return env_path
    if os.path.isabs(file_name):
        return file_name

    # Place logs beside WOM.py (../ehb_log.csv) instead of depending on cwd
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, file_name)


def log_ehb_to_csv(username, ehb, file_name="ehb_log.csv", print_csv_changes=True):
    """Logs the username, EHB value, and timestamp to a CSV file."""
    resolved_path = _resolve_csv_path(file_name)
    try:
        with open(resolved_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, username, ehb])
            if print_csv_changes:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(
                    f"{timestamp} - Logged {username} with {ehb} EHB at {timestamp} "
                    f"to {resolved_path}."
                )
    except Exception as e:
        print(f"Error logging to CSV at {resolved_path}: {e}")
