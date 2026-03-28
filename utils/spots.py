from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

SPOTS_FILE = Path(r"C:\poker_tools\spots.json")


def ensure_spots_file() -> None:
    """Create the spots file if it does not exist yet."""
    if not SPOTS_FILE.exists():
        SPOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPOTS_FILE.write_text("{}", encoding="utf-8")


def load_spots() -> Dict[str, Dict[str, Any]]:
    """Load all saved spots from disk."""
    ensure_spots_file()
    try:
        with SPOTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("spots.json root must be an object")
        return data
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse spots file: {SPOTS_FILE}")


def save_spots(spots: Dict[str, Dict[str, Any]]) -> None:
    """Write all saved spots to disk."""
    SPOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SPOTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(spots, f, indent=2, sort_keys=True)


def get_spot(name: str) -> Dict[str, Any]:
    """Return one saved spot by name."""
    spots = load_spots()
    if name not in spots:
        raise ValueError(f"Saved spot not found: {name}")
    return spots[name]


def upsert_spot(name: str, values: Dict[str, Any]) -> None:
    """Create or overwrite a saved spot."""
    spots = load_spots()
    spots[name] = values
    save_spots(spots)


def resolve_value(cli_value, spot_data: dict, key: str):
    """Prefer CLI value if provided, otherwise use saved spot value."""
    if cli_value is not None:
        return cli_value
    return spot_data.get(key)