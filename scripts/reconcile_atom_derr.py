#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATOM tracking seed + SHORT DERR qty reconcile (Binance gerçeklik)."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

from config import BinanceConfig  # noqa: E402
from mina_position_manager import MinaPositionManager  # noqa: E402
from mina_trading_journal import TradingJournal  # noqa: E402
import mina_tracking as mt  # noqa: E402

ATOM_SYMBOL = "ATOMUSDT"
ATOM_SIDE = "LONG"
SHORT_RECONCILE = [
    ("XRPUSDT", "SHORT", 32),
    ("ADAUSDT", "SHORT", 33),
    ("DOTUSDT", "SHORT", 34),
]


def read_binance_pos(client, symbol: str, side: str):
    for p in client.futures_position_information():
        if p["symbol"] != symbol:
            continue
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        ps = "LONG" if amt > 0 else "SHORT"
        if ps != side:
            continue
        return {
            "entry": float(p.get("entryPrice") or 0),
            "qty": abs(amt),
            "margin": float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0),
            "leverage": int(float(p.get("leverage") or 4)),
            "mark": float(p.get("markPrice") or 0),
        }
    return None


def seed_atom_tracking(client, manager: MinaPositionManager) -> None:
    pos = read_binance_pos(client, ATOM_SYMBOL, ATOM_SIDE)
    if not pos:
        print(f"FAIL: Binance'te {ATOM_SYMBOL} {ATOM_SIDE} yok")
        sys.exit(1)

    key = mt.pos_key(ATOM_SYMBOL, ATOM_SIDE)
    entry = pos["entry"]
    margin = pos["margin"]
    mark = pos["mark"] or entry

    initial_prices = mt.load_json(mt.INITIAL_PRICE_FILE)
    initial_margins = mt.load_json(mt.INITIAL_MARGIN_FILE)
    defense_levels = mt.load_json(mt.DEFENSE_FILE)
    tp_levels = mt.load_json(mt.TP_FILE)
    max_prices = mt.load_json(mt.MAX_PRICE_FILE)

    initial_prices[key] = entry
    initial_margins[key] = round(margin, 4)
    defense_levels[key] = 0
    tp_levels[key] = 0
    max_prices[key] = mark

    mt.save_json(mt.INITIAL_PRICE_FILE, initial_prices)
    mt.save_json(mt.INITIAL_MARGIN_FILE, initial_margins)
    mt.save_json(mt.DEFENSE_FILE, defense_levels)
    mt.save_json(mt.TP_FILE, tp_levels)
    mt.save_json(mt.MAX_PRICE_FILE, max_prices)

    manager.init_position_state(ATOM_SYMBOL, entry)
    state = manager.position_states.get(ATOM_SYMBOL, {})
    state["initial_margin"] = margin
    state["defense_stage"] = 0
    state["tp1_done"] = False
    state["tp2_done"] = False
    state["highest_price"] = mark
    state["weighted_avg_price"] = entry
    manager._save_state()

    print(f"OK ATOM seed: entry={entry} qty={pos['qty']} margin={margin:.4f} mark={mark}")
    print(f"  {mt.INITIAL_PRICE_FILE}[{key}]={entry}")
    print(f"  mina_position_state[{ATOM_SYMBOL}] yazildi")


def reconcile_shorts(client, journal: TradingJournal) -> None:
    for symbol, side, trade_id in SHORT_RECONCILE:
        pos = read_binance_pos(client, symbol, side)
        if not pos:
            print(f"FAIL: Binance'te {symbol} {side} yok")
            continue

        cursor = journal.conn.cursor()
        cursor.execute(
            "SELECT open_qty, initial_margin FROM trades WHERE id=? AND status='open'",
            (trade_id,),
        )
        row = cursor.fetchone()
        if not row:
            print(f"FAIL: DERR id={trade_id} acik kayit yok")
            continue

        old_qty = float(row["open_qty"])
        old_margin = float(row["initial_margin"])
        new_qty = pos["qty"]
        new_margin = pos["margin"]

        if abs(old_qty - new_qty) < 1e-8 and abs(old_margin - new_margin) < 0.01:
            print(f"OK {symbol} {side} id={trade_id} zaten uyumlu qty={new_qty}")
            continue

        ok = journal.reconcile_open_qty(trade_id, new_qty, new_margin)
        print(
            f"{'OK' if ok else 'FAIL'} {symbol} {side} id={trade_id}: "
            f"qty {old_qty} -> {new_qty}, margin {old_margin:.4f} -> {new_margin:.4f}"
        )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    client = BinanceConfig().get_client()
    journal = TradingJournal(db_path=os.path.join(ROOT, "mina_trading_journal.db"))
    manager = MinaPositionManager(client, slot_size=500, journal=journal, data_root=ROOT)

    print("=== ATOM tracking seed ===")
    seed_atom_tracking(client, manager)

    print("\n=== SHORT DERR reconcile ===")
    reconcile_shorts(client, journal)

    print("\n=== Dogrulama ===")
    key = mt.pos_key(ATOM_SYMBOL, ATOM_SIDE)
    for fn in (mt.INITIAL_PRICE_FILE, mt.INITIAL_MARGIN_FILE, mt.DEFENSE_FILE, mt.MAX_PRICE_FILE):
        data = mt.load_json(fn)
        print(f"  {fn}[{key}] = {data.get(key, 'EKSIK')}")

    state = mt.load_json("mina_position_state.json")
    print(f"  mina_position_state[ATOMUSDT] = {json.dumps(state.get('ATOMUSDT'), ensure_ascii=False)}")

    cursor = journal.conn.cursor()
    for symbol, side, trade_id in SHORT_RECONCILE:
        row = cursor.execute(
            "SELECT open_qty, initial_margin FROM trades WHERE id=?", (trade_id,)
        ).fetchone()
        pos = read_binance_pos(client, symbol, side)
        match = pos and abs(float(row["open_qty"]) - pos["qty"]) < 1e-6
        print(
            f"  {symbol} DERR qty={row['open_qty']} Binance qty={pos['qty'] if pos else '?'} "
            f"{'OK' if match else 'UYUMSUZ'}"
        )

    journal.close()


if __name__ == "__main__":
    main()
