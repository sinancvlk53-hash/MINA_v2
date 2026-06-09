# -*- coding: utf-8 -*-
"""Dashboard / motor ayarları — dashboard_settings.json."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "dashboard_settings.json")
MOTOR_PAUSE_FILE = os.path.join(ROOT, "motor_paused.flag")

VALID_STRATEGY_MODES = frozenset({"defense", "stop", "ht", "full_manual"})

DEFAULT_LEVERAGE_STRATEGY: Dict[str, str] = {
    "1": "defense",
    "2": "defense",
    "3": "defense",
    "5": "defense",
    "10": "defense",
}

HT_STOP_PCT = 2.0

DEFAULTS: Dict[str, Any] = {
    "merterTimeStopH": 4,
    "halukTimeStopH": 8,
    "breakevenMult": 1.0020,
    "dailyLossLimitPct": 20,
    "telegramNotify": True,
    "motorActive": True,
    "leverageStrategy": dict(DEFAULT_LEVERAGE_STRATEGY),
}

DAILY_LOSS_KILL_FILE = os.path.join(ROOT, "daily_loss_kill.flag")
DAILY_RISK_STATE_FILE = os.path.join(ROOT, "daily_risk_state.json")


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
    strat = dict(DEFAULT_LEVERAGE_STRATEGY)
    if isinstance(data.get("leverageStrategy"), dict):
        strat.update({
            str(k): v for k, v in data["leverageStrategy"].items()
            if v in VALID_STRATEGY_MODES
        })
    data["leverageStrategy"] = strat
    data["motorActive"] = not os.path.isfile(MOTOR_PAUSE_FILE)
    return data


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = load_settings()
    allowed = set(DEFAULTS.keys())
    for k, v in updates.items():
        if k not in allowed:
            continue
        if k == "leverageStrategy" and isinstance(v, dict):
            strat = dict(current.get("leverageStrategy") or DEFAULT_LEVERAGE_STRATEGY)
            for lev, mode in v.items():
                key = str(lev)
                if key in DEFAULT_LEVERAGE_STRATEGY and mode in VALID_STRATEGY_MODES:
                    strat[key] = mode
            current["leverageStrategy"] = strat
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


def daily_loss_limit_pct() -> float:
    raw = load_settings().get("dailyLossLimitPct", DEFAULTS["dailyLossLimitPct"])
    try:
        pct = float(raw)
    except (TypeError, ValueError):
        pct = float(DEFAULTS["dailyLossLimitPct"])
    return max(1.0, min(pct, 50.0))


def is_daily_loss_kill_active() -> bool:
    return os.path.isfile(DAILY_LOSS_KILL_FILE)


def set_daily_loss_kill(active: bool) -> None:
    if active:
        try:
            with open(DAILY_LOSS_KILL_FILE, "w", encoding="utf-8") as f:
                f.write("kill\n")
        except OSError:
            pass
    else:
        try:
            if os.path.isfile(DAILY_LOSS_KILL_FILE):
                os.remove(DAILY_LOSS_KILL_FILE)
        except OSError:
            pass


def load_daily_risk_state() -> Dict[str, Any]:
    if os.path.isfile(DAILY_RISK_STATE_FILE):
        try:
            with open(DAILY_RISK_STATE_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                return raw
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_daily_risk_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(DAILY_RISK_STATE_FILE) or ROOT, exist_ok=True)
    with open(DAILY_RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_new_entries_blocked() -> bool:
    """Tam günlük zarar limiti — yeni pozisyon açma engeli."""
    return is_daily_loss_kill_active()


def leverage_strategy_mode(leverage: int) -> str:
    """4x her zaman savunma; diğerleri dashboard ayarından."""
    if leverage == 4:
        return "defense"
    strat = load_settings().get("leverageStrategy") or DEFAULT_LEVERAGE_STRATEGY
    mode = strat.get(str(leverage), "defense")
    return mode if mode in VALID_STRATEGY_MODES else "defense"


def entry_margin_for_leverage(leverage: int, slot: float) -> float:
    """Giriş marjini — full_manual: tam slot, diğer modlar: slot/5."""
    if leverage == 4:
        return slot / 5
    if leverage_strategy_mode(leverage) == "full_manual":
        return float(slot)
    return float(slot) / 5
