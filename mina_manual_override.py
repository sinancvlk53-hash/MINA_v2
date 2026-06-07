# -*- coding: utf-8 -*-
"""Manuel yönetim modu — pozisyon bazlı stop/TP override."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set

import mina_tracking as mt

MANUAL_OVERRIDE_FILE = "manual_override.json"


def _root(data_root: Optional[str] = None) -> str:
    return data_root or os.environ.get("MINA_DATA_ROOT", mt.DATA_ROOT)


def load_all(data_root: Optional[str] = None) -> Dict[str, Any]:
    if data_root:
        return _load_path(os.path.join(_root(data_root), MANUAL_OVERRIDE_FILE))
    return mt.load_json(MANUAL_OVERRIDE_FILE)


def _load_path(path: str) -> Dict[str, Any]:
    try:
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_all(data: Dict[str, Any], data_root: Optional[str] = None) -> None:
    root = _root(data_root)
    path = os.path.join(root, MANUAL_OVERRIDE_FILE)
    os.makedirs(root, exist_ok=True)
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_override(pos_key: str, data_root: Optional[str] = None) -> Dict[str, Any]:
    data = load_all(data_root)
    row = data.get(pos_key) or {}
    return {
        "active": bool(row.get("active")),
        "stop": row.get("stop"),
        "tp": row.get("tp"),
    }


def set_override(
    pos_key: str,
    *,
    active: bool,
    stop: Optional[float] = None,
    tp: Optional[float] = None,
    data_root: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_all(data_root)
    if not active:
        data.pop(pos_key, None)
    else:
        entry: Dict[str, Any] = {"active": True}
        if stop is not None and stop > 0:
            entry["stop"] = float(stop)
        if tp is not None and tp > 0:
            entry["tp"] = float(tp)
        data[pos_key] = entry
    save_all(data, data_root)
    return get_override(pos_key, data_root)


def clear_override(pos_key: str, data_root: Optional[str] = None) -> None:
    data = load_all(data_root)
    if pos_key in data:
        del data[pos_key]
        save_all(data, data_root)


def clear_stale(open_keys: Set[str], data_root: Optional[str] = None) -> int:
    """Kapalı pozisyonların manuel override kaydını sil."""
    data = load_all(data_root)
    removed = 0
    for key in list(data.keys()):
        if key not in open_keys:
            del data[key]
            removed += 1
    if removed:
        save_all(data, data_root)
    return removed
