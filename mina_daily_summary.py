# -*- coding: utf-8 -*-
"""Gece 23:00 günlük PnL özeti Telegram bildirimi."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Optional

STATE_FILE = "daily_summary_state.json"


def _state_path(data_root: Optional[str] = None) -> str:
    root = data_root or os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, STATE_FILE)


def _load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
            return raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def maybe_send_daily_summary(
    *,
    journal,
    balance: float,
    data_root: Optional[str] = None,
    hour: int = 23,
) -> bool:
    """Saat `hour` iken günde bir kez özet gönder."""
    now = datetime.now()
    today = date.today().isoformat()
    path = _state_path(data_root)
    state = _load_state(path)

    if state.get("date") == today and state.get("sent"):
        return False
    if now.hour != hour:
        return False

    try:
        today_pnl = journal.get_today_realized_pnl()
        stats = journal.get_today_trade_stats()
    except Exception as exc:
        print(f"⚠️  daily summary stats: {exc}")
        return False

    try:
        from mina_motor_telegram import notify_daily_summary
        notify_daily_summary(
            today_pnl=today_pnl,
            trade_count=int(stats.get("count") or 0),
            wins=int(stats.get("wins") or 0),
            losses=int(stats.get("losses") or 0),
            balance=float(balance or 0),
        )
    except Exception as exc:
        print(f"⚠️  daily summary send: {exc}")
        return False

    _save_state(path, {"date": today, "sent": True, "hour": hour})
    print(f"📊 Günlük özet gönderildi — PnL {today_pnl:+.2f} USDT")
    return True


def reset_daily_summary_if_new_day(data_root: Optional[str] = None) -> None:
    """Gece yarısı sayaç sıfırlama (main döngüsünden)."""
    today = date.today().isoformat()
    path = _state_path(data_root)
    state = _load_state(path)
    if state.get("date") != today:
        _save_state(path, {"date": today, "sent": False})
