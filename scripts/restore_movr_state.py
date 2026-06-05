#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOVRUSDT merter_other state geri yükle — Binance gerçekliği → merter_dca_state.json.
Motor tracking kirini temizler (MOVRUSDT_LONG).
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

TP1_PCT = 0.03
TP2_PCT = 0.05
TRAIL_PCT = 0.02
YUVA = "merter_other"
SYMBOL = "MOVRUSDT"
STATE_FILE = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
TRACKING_FILES = (
    "initial_prices.json",
    "initial_margins.json",
    "defense_levels.json",
    "tp_levels.json",
    "max_prices.json",
)


def _load_state() -> dict:
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"positions": {}, "pending_confirm": {}}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _clear_motor_tracking() -> None:
    key = f"{SYMBOL}_LONG"
    for fname in TRACKING_FILES:
        path = os.path.join(ROOT, fname)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if key in data:
            data.pop(key, None)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            print(f"  motor tracking temizlendi: {fname}")


def restore_movr() -> dict:
    from backend.config import BinanceConfig, AccountManager
    from signal_bot.merter_dca_manager import PARTS_PER_YUVA, TOTAL_SLOTS

    client = BinanceConfig().get_client()
    pos = None
    for p in client.futures_position_information(symbol=SYMBOL):
        if float(p["positionAmt"]) != 0:
            pos = p
            break
    if not pos:
        raise RuntimeError(f"{SYMBOL} Binance'te açık pozisyon yok")

    qty = abs(float(pos["positionAmt"]))
    avg = float(pos["entryPrice"])
    mark = float(pos.get("markPrice") or avg)
    margin = float(pos.get("isolatedMargin") or 0)

    import sqlite3
    conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, open_time, open_price FROM trades WHERE symbol=? AND status='open' AND leverage=1",
        (SYMBOL,),
    ).fetchone()
    conn.close()
    if not row:
        raise RuntimeError("Journal'da açık MOVR trade yok")
    trade_id = int(row["id"])
    entry_anchor = float(row["open_price"])
    opened_at = str(row["open_time"]).replace(" ", "T") + "Z"

    bal = AccountManager(client).get_usdt_balance()
    part_usdt = (bal / TOTAL_SLOTS) / PARTS_PER_YUVA
    total_cost = qty * avg
    parts_filled = max(1, min(PARTS_PER_YUVA, int(round(total_cost / part_usdt)) if part_usdt else 1))

    open_limits: list = []
    try:
        for o in client.futures_get_open_orders(symbol=SYMBOL):
            if o.get("side") == "BUY" and o.get("type") == "LIMIT":
                open_limits.append(int(o["orderId"]))
    except Exception as exc:
        print(f"  uyarı: açık emirler okunamadı ({exc}) — limit_order_ids boş")

    tp1 = avg * (1 + TP1_PCT)
    tp2 = avg * (1 + TP2_PCT)
    tp1_done = mark >= tp1
    trailing_active = tp1_done and mark >= tp2

    restored = {
        "symbol": SYMBOL,
        "signal_source": YUVA,
        "trade_id": trade_id,
        "entry_anchor": entry_anchor,
        "parts_filled": parts_filled,
        "parts_total": PARTS_PER_YUVA,
        "total_qty": qty,
        "total_cost": total_cost,
        "avg_price": avg,
        "opened_at": opened_at,
        "tp1_done": tp1_done,
        "trailing_active": trailing_active,
        "trailing_peak": mark if trailing_active else None,
        "breakeven_mode": False,
        "breakeven_since": None,
        "limit_order_ids": open_limits,
        "part_usdt": part_usdt,
        "restored_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restore_note": "Binance sync — motor hayalet/TP1 müdahalesi sonrası",
    }

    state = _load_state()
    state.setdefault("positions", {})[YUVA] = restored
    _save_state(state)

    print("MOVR state geri yüklendi:")
    print(json.dumps(restored, indent=2, ensure_ascii=False))
    print(f"\nTP1={tp1:.6f} TP2={tp2:.6f} mark={mark:.6f}")
    print(f"tp1_done={tp1_done} trailing_active={trailing_active}")
    print(f"parts_filled={parts_filled}/{PARTS_PER_YUVA} open_limits={open_limits}")

    print("\nMotor tracking temizliği:")
    _clear_motor_tracking()
    return restored


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    restore_movr()
