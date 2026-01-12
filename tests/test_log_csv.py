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


def test_log_ehb_to_csv_writes_row(tmp_path):
    target = tmp_path / "ehb_log.csv"

    log_csv.log_ehb_to_csv("player", 123, file_name=str(target), print_csv_changes=False)

    with open(target, newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))

    assert len(rows) == 1
    assert rows[0][1:] == ["player", "123"]
