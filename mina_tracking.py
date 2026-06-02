# -*- coding: utf-8 -*-
"""MINA v2 — kök dizin state JSON dosyaları (tek kaynak)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

DATA_ROOT = os.environ.get(
    "MINA_DATA_ROOT",
    os.path.dirname(os.path.abspath(__file__)),
)

DEFENSE_FILE = "defense_levels.json"
TP_FILE = "tp_levels.json"
MAX_PRICE_FILE = "max_prices.json"
INITIAL_MARGIN_FILE = "initial_margins.json"
STOP_LEVELS_FILE = "stop_levels.json"
PENDING_ORDERS_FILE = "pending_orders.json"
INITIAL_PRICE_FILE = "initial_entry_prices.json"
DEFENSE_STOPS_FILE = "defense_stop_orders.json"

TRACKING_FILES = (
    DEFENSE_FILE,
    TP_FILE,
    MAX_PRICE_FILE,
    INITIAL_MARGIN_FILE,
    STOP_LEVELS_FILE,
    PENDING_ORDERS_FILE,
    INITIAL_PRICE_FILE,
    DEFENSE_STOPS_FILE,
)


def pos_key(symbol: str, side: str) -> str:
    return f"{symbol}_{side}"


def _path(filename: str) -> str:
    return os.path.join(DATA_ROOT, filename)


def load_json(filename: str) -> Dict[str, Any]:
    path = _path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(filename: str, data: Dict[str, Any]) -> None:
    path = _path(filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def dump_all_tracking() -> None:
    """Tüm tracking dosyalarını ham JSON olarak stdout'a yaz."""
    for fn in TRACKING_FILES:
        data = load_json(fn)
        print(f"===== {fn} =====")
        print(json.dumps(data, indent=2, ensure_ascii=False))
