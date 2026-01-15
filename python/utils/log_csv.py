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


def load_latest_ehb_from_csv(file_name="ehb_log.csv"):
    """Return a mapping of username -> latest EHB value from the CSV log."""
    resolved_path = _resolve_csv_path(file_name)
    if not os.path.exists(resolved_path):
        return {}

    latest = {}
    try:
        with open(resolved_path, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) < 3:
                    continue
                timestamp = row[0].strip()
                username = row[1].strip()
                ehb_raw = row[2].strip()
                try:
                    ehb = float(ehb_raw)
                except ValueError:
                    continue
                prev = latest.get(username)
                if prev is None or timestamp > prev["timestamp"]:
                    latest[username] = {"timestamp": timestamp, "ehb": ehb}
    except Exception as e:
        print(f"Error reading CSV log at {resolved_path}: {e}")
        return {}

    return {username: data["ehb"] for username, data in latest.items()}
