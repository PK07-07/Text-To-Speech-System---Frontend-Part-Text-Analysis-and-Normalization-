"""Runtime package data loader for text_frontend."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def load_abbreviations_data() -> dict:
    """Loads bundled abbreviations.json."""
    path = DATA_DIR / "abbreviations.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_words_set() -> frozenset[str]:
    """Loads bundled words.txt as a frozenset of lowercase words."""
    path = DATA_DIR / "words.txt"
    with open(path, "r", encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


@lru_cache(maxsize=1)
def load_emoji_data() -> dict[str, str]:
    """Loads bundled emoji_names.json if present."""
    path = DATA_DIR / "emoji_names.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_airports_data() -> frozenset[str]:
    """Loads bundled airports.json as a frozenset of uppercase IATA airport codes."""
    path = DATA_DIR / "airports.json"
    if not path.exists():
        return frozenset()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return frozenset(c.upper() for c in data.get("airports", []))
