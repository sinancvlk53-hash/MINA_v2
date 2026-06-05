#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC LONG 04:59 kökeni + MOVR tam log."""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)


def sep(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def btc_investigation():
    sep("SORU 1 — BTCUSDT LONG kökeni")
    queue_path = f"{ROOT}/signal_bot/raw_signal_queue.json"
    with open(queue_path, encoding="utf-8") as f:
        queue = json.load(f)

    btc_entries = []
    for i, e in enumerate(queue.get("entries") or []):
        sym = (e.get("symbol") or "").upper()
        if "BTC" in sym and sym.endswith("USDT"):
            btc_entries.append((i, e))

    print(f"raw_signal_queue.json — BTC* entries: {len(btc_entries)}")
    for i, e in btc_entries[-15:]:
        print(
            f"  [{i}] ts={e.get('timestamp')} src={e.get('source')} "
            f"sym={e.get('symbol')} dir={e.get('direction')} status={e.get('status')} "
            f"entry={e.get('entry_price')} stop={e.get('stop_price')}"
        )

    # LONG approved specifically
    print("\n--- BTCUSDT LONG (approved/pending) ---")
    for i, e in btc_entries:
        sym = (e.get("symbol") or "").upper()
        d = (e.get("direction") or "").upper()
        if sym == "BTCUSDT" and d == "LONG":
            print(json.dumps(e, ensure_ascii=False, indent=2, default=str))

    db = f"{ROOT}/mina_trading_journal.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    print("\n--- signal_decisions BTC ---")
    try:
        rows = conn.execute(
            """
            SELECT id, merter_symbol, merter_direction, k2_label, k3_action, created_at, scenario_label
            FROM signal_decisions
            WHERE merter_symbol LIKE '%BTC%'
            ORDER BY created_at DESC LIMIT 20
            """
        ).fetchall()
        for r in rows:
            print(dict(r))
    except Exception as ex:
        print(f"signal_decisions: {ex}")

    print("\n--- trades BTC id 24-25 ---")
    for r in conn.execute(
        "SELECT * FROM trades WHERE symbol='BTCUSDT' AND id >= 24 ORDER BY id"
    ).fetchall():
        print(dict(r))

    conn.close()

    print("\n--- mina_bot.log 04:58-05:02 ---")
    p = subprocess.run(
        ["grep", "2026-06-05 04:5", f"{ROOT}/mina_bot.log"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for ln in p.stdout.splitlines():
        if "BTC" in ln.upper() or "slot" in ln.lower() or "MZ" in ln or "fill" in ln.lower():
            print(ln)

    print("\n--- position_sources.json BTC ---")
    ps = json.load(open(f"{ROOT}/position_sources.json"))
    for k, v in ps.items():
        if "BTC" in k:
            print(f"  {k}: {v}")

    print("\n--- pending_orders.json ---")
    po = json.load(open(f"{ROOT}/pending_orders.json")) if os.path.isfile(f"{ROOT}/pending_orders.json") else {}
    for k, v in po.items():
        if "BTC" in k.upper():
            print(f"  {k}: {v}")


def movr_investigation():
    sep("SORU 2 — MOVRUSDT tam durum")
    state_path = f"{ROOT}/signal_bot/merter_dca_state.json"
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    print("merter_dca_state.json — MOVR / merter_other:")
    positions = state.get("positions") or {}
    if "merter_other" in positions:
        print(json.dumps(positions["merter_other"], indent=2, ensure_ascii=False))
    else:
        print("  merter_other YOK (state'te kayıt yok!)")
    for yuva, p in positions.items():
        if (p.get("symbol") or "").upper() == "MOVRUSDT":
            print(f"\n{yuva}:")
            print(json.dumps(p, indent=2, ensure_ascii=False))

    print("\n--- merter_dca.log TÜM MOVR satırları ---")
    p = subprocess.run(
        ["grep", "-i", "MOVR", f"{ROOT}/signal_bot/merter_dca.log"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for ln in p.stdout.splitlines():
        print(ln)

    print("\n--- mina_bot.log MOVR TP/kapat ---")
    p2 = subprocess.run(
        ["grep", "-i", "MOVR", f"{ROOT}/mina_bot.log"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for ln in p2.stdout.splitlines():
        if any(x in ln.upper() for x in ("TP", "KAPAT", "TRAIL", "CLOSE", "HAYALET", "take_profit")):
            print(ln)

    conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM trades WHERE symbol='MOVRUSDT'").fetchone()
    if r:
        print("\n--- journal MOVR trade ---")
        print(dict(r))
    conn.close()

    print("\n--- Binance MOVR anlık ---")
    from backend.config import BinanceConfig
    client = BinanceConfig().get_client()
    for p in client.futures_position_information(symbol="MOVRUSDT"):
        amt = float(p["positionAmt"])
        if amt == 0:
            continue
        print(
            f"qty={abs(amt)} entry={p['entryPrice']} mark={p.get('markPrice')} "
            f"lev={p['leverage']} upnl={p['unRealizedProfit']} margin={p.get('isolatedMargin')}"
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    btc_investigation()
    movr_investigation()
