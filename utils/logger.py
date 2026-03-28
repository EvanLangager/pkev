import csv
from pathlib import Path
from datetime import datetime

def append_log_row(path: str, headers: list[str], row: dict):
    p = Path(path)
    file_exists = p.exists()

    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def timestamp():
    return datetime.now().isoformat(timespec="seconds")