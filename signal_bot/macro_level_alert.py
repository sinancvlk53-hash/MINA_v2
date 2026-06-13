# -*- coding: utf-8 -*-
"""Makro destek/direnç yakınlık alarmları — macro_levels.json + macro_prices."""

from __future__ import annotations

import json
import os
import time

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
LEVELS_PATH = os.path.join(ROOT, "signal_bot/macro_levels.json")
ALERT_STATE_PATH = os.path.join(ROOT, "signal_bot/macro_level_alert_state.json")
THRESHOLD_PCT = 3.0  # seviyeye %3 yaklaşınca bildir
COOLDOWN_SEC = 3600  # aynı seviye için 1 saat cooldown


def _load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _iter_level_rows(levels_raw):
    """macro_levels.json → coin satırları."""
    if isinstance(levels_raw, list):
        return levels_raw
    if isinstance(levels_raw, dict):
        rows = levels_raw.get("levels")
        if isinstance(rows, list):
            return rows
        # eski/düz dict formatı: {coin: {...}}
        out = []
        for coin, data in levels_raw.items():
            if coin in ("updated_at", "source", "levels"):
                continue
            if isinstance(data, dict):
                row = dict(data)
                row.setdefault("coin", coin)
                out.append(row)
        return out
    return []


def check_level_alerts(macro_prices: dict):
    """
    macro_levels.json'daki destek/direnç seviyelerine
    güncel fiyat %3 yaklaşınca Telegram bildirimi gönder.
    """
    try:
        from mina_motor_telegram import send_telegram
    except Exception:
        return

    levels_raw = _load_json(LEVELS_PATH)
    state = _load_json(ALERT_STATE_PATH, {})
    now = time.time()
    alerts = []

    for data in _iter_level_rows(levels_raw):
        if not isinstance(data, dict):
            continue
        coin = data.get("coin")
        if not coin:
            continue

        price_data = macro_prices.get(coin, {})
        if not isinstance(price_data, dict):
            continue
        current = float(price_data.get("value", 0) or 0)
        if current <= 0:
            continue

        supports = [float(x) for x in (data.get("supports") or data.get("support") or []) if x]
        resistances = [float(x) for x in (data.get("resistances") or data.get("resistance") or []) if x]

        for level in supports:
            if level <= 0:
                continue
            pct = abs(current - level) / level * 100
            key = f"{coin}_sup_{level}"
            last = state.get(key, 0)
            if pct <= THRESHOLD_PCT and (now - last) > COOLDOWN_SEC:
                alerts.append(
                    f"🟢 {coin} DESTEK yakını!\n"
                    f"Fiyat: {current:,.2f} → Destek: {level:,.2f} ({pct:.1f}% uzakta)"
                )
                state[key] = now

        for level in resistances:
            if level <= 0:
                continue
            pct = abs(current - level) / level * 100
            key = f"{coin}_res_{level}"
            last = state.get(key, 0)
            if pct <= THRESHOLD_PCT and (now - last) > COOLDOWN_SEC:
                alerts.append(
                    f"🔴 {coin} DİRENÇ yakını!\n"
                    f"Fiyat: {current:,.2f} → Direnç: {level:,.2f} ({pct:.1f}% uzakta)"
                )
                state[key] = now

    _save_json(ALERT_STATE_PATH, state)

    if alerts:
        msg = "📊 MAKRO SEVİYE ALARMI\n━━━━━━━━━━━━\n" + "\n\n".join(alerts)
        send_telegram(msg)
        print(f"[LEVEL ALERT] {len(alerts)} alarm gönderildi")
