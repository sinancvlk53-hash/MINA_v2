# -*- coding: utf-8 -*-
"""Sistem uyarıları — debounced Telegram bildirimleri."""

from __future__ import annotations

import time
from typing import Dict

_last_sent: Dict[str, float] = {}
_DEFAULT_COOLDOWN = 300.0


def _should_send(key: str, cooldown: float) -> bool:
    now = time.time()
    last = _last_sent.get(key, 0.0)
    if now - last < cooldown:
        return False
    _last_sent[key] = now
    return True


def alert_rate_limit(detail: str, cooldown: float = _DEFAULT_COOLDOWN) -> None:
    if not _should_send("rate_limit", cooldown):
        return
    try:
        from mina_motor_telegram import notify_system_alert
        notify_system_alert("rate_limit", detail)
    except Exception as exc:
        print(f"⚠️  rate_limit alert: {exc}")


def alert_database_lock(detail: str, cooldown: float = 120.0) -> None:
    if not _should_send("database_lock", cooldown):
        return
    try:
        from mina_motor_telegram import notify_system_alert
        notify_system_alert("database_lock", detail)
    except Exception as exc:
        print(f"⚠️  database_lock alert: {exc}")


def alert_service_down(service: str, detail: str = "", cooldown: float = 600.0) -> None:
    key = f"service_down:{service}"
    if not _should_send(key, cooldown):
        return
    try:
        from mina_motor_telegram import notify_system_alert
        msg = service if not detail else f"{service}\n{detail}"
        notify_system_alert("service_down", msg)
    except Exception as exc:
        print(f"⚠️  service_down alert: {exc}")
