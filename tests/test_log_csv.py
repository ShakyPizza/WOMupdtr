import csv
import os
import sys

# Add repository root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python.utils import log_csv


def test_resolve_csv_path_returns_absolute_path_for_relative():
    expected_base = os.path.abspath(os.path.join(os.path.dirname(log_csv.__file__), ".."))
    expected_path = os.path.join(expected_base, "ehb_log.csv")

    assert log_csv._resolve_csv_path("ehb_log.csv") == expected_path


def test_resolve_csv_path_keeps_absolute_path(tmp_path):
    absolute = tmp_path / "custom.csv"

    assert log_csv._resolve_csv_path(str(absolute)) == str(absolute)


def test_log_ehb_to_csv_writes_row(monkeypatch, tmp_path):
    target = tmp_path / "ehb_log.csv"
    monkeypatch.setenv("WOM_DATABASE_PATH", str(tmp_path / "database.db"))

    log_csv.log_ehb_to_csv("player", 123, file_name=str(target), print_csv_changes=False)

    with open(target, newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))

    assert len(rows) == 1
    assert rows[0][1:] == ["player", "123"]


# --- EHB_LOG_PATH env var ---

def test_resolve_csv_path_uses_env_var(monkeypatch, tmp_path):
    env_path = str(tmp_path / "env_log.csv")
    monkeypatch.setenv("EHB_LOG_PATH", env_path)
    assert log_csv._resolve_csv_path("ehb_log.csv") == env_path


def test_log_ehb_to_csv_respects_ehb_log_path_env_var(monkeypatch, tmp_path):
    target = tmp_path / "env_log.csv"
    monkeypatch.setenv("EHB_LOG_PATH", str(target))
    monkeypatch.setenv("WOM_DATABASE_PATH", str(tmp_path / "database.db"))

    log_csv.log_ehb_to_csv("player", 99, print_csv_changes=False)

    with open(target, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 1
    assert rows[0][1:] == ["player", "99"]


# --- load_latest_ehb_from_csv ---

def test_load_latest_ehb_from_csv_returns_empty_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EHB_LOG_PATH", str(tmp_path / "nonexistent.csv"))
    assert log_csv.load_latest_ehb_from_csv() == {}


def test_load_latest_ehb_from_csv_returns_latest_per_player(tmp_path):
    target = tmp_path / "ehb_log.csv"
    with open(target, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["2024-01-01 10:00:00", "alice", "100.0"])
        writer.writerow(["2024-01-02 10:00:00", "alice", "150.0"])  # later → wins
        writer.writerow(["2024-01-01 10:00:00", "bob", "200.0"])

    result = log_csv.load_latest_ehb_from_csv(file_name=str(target))

    assert result == {"alice": 150.0, "bob": 200.0}


def test_load_latest_ehb_from_csv_skips_malformed_rows(tmp_path):
    target = tmp_path / "ehb_log.csv"
    with open(target, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["2024-01-01 10:00:00", "alice", "not_a_number"])
        writer.writerow(["short_row"])
        writer.writerow(["2024-01-01 10:00:00", "bob", "42.5"])

    result = log_csv.load_latest_ehb_from_csv(file_name=str(target))

    assert result == {"bob": 42.5}
    assert "alice" not in result
