# -*- coding: utf-8 -*-
"""Dashboard / motor ayarları — dashboard_settings.json."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "dashboard_settings.json")
MOTOR_PAUSE_FILE = os.path.join(ROOT, "motor_paused.flag")

DEFAULTS: Dict[str, Any] = {
    "merterTimeStopH": 4,
    "halukTimeStopH": 8,
    "breakevenMult": 1.0020,
    "telegramNotify": True,
    "motorActive": True,
}


def load_settings() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    data["motorActive"] = not os.path.isfile(MOTOR_PAUSE_FILE)
    return data


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = load_settings()
    allowed = set(DEFAULTS.keys())
    for k, v in updates.items():
        if k not in allowed:
            continue
        current[k] = v

    motor_active = bool(current.get("motorActive", True))
    if motor_active:
        try:
            if os.path.isfile(MOTOR_PAUSE_FILE):
                os.remove(MOTOR_PAUSE_FILE)
        except OSError:
            pass
    else:
        try:
            with open(MOTOR_PAUSE_FILE, "w", encoding="utf-8") as f:
                f.write("paused\n")
        except OSError:
            pass

    payload = {k: current[k] for k in DEFAULTS if k != "motorActive"}
    payload["motorActive"] = motor_active
    os.makedirs(os.path.dirname(SETTINGS_FILE) or ROOT, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return load_settings()


def is_motor_paused() -> bool:
    return os.path.isfile(MOTOR_PAUSE_FILE)


def merter_time_stop_h() -> float:
    return float(load_settings().get("merterTimeStopH") or DEFAULTS["merterTimeStopH"])


def haluk_time_stop_h() -> float:
    return float(load_settings().get("halukTimeStopH") or DEFAULTS["halukTimeStopH"])


def breakeven_mult() -> float:
    return float(load_settings().get("breakevenMult") or DEFAULTS["breakevenMult"])
