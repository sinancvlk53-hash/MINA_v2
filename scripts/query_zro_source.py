#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZROUSDT LONG signal_source kökeni."""
import json
import os
import sqlite3
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)

print("=== position_sources.json ZRO ===")
ps = json.load(open(f"{ROOT}/position_sources.json"))
for k, v in ps.items():
    if "ZRO" in k:
        print(f"  {k}: {v}")

print("\n=== DERR trades ZROUSDT (tümü) ===")
conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
for r in conn.execute(
    "SELECT id, symbol, side, leverage, status, open_time, close_time, "
    "close_reason, signal_source, open_price, close_price, pnl_usdt "
    "FROM trades WHERE symbol='ZROUSDT' ORDER BY id"
).fetchall():
    print(dict(r))

print("\n=== merter_dca_state.json ===")
state = json.load(open(f"{ROOT}/signal_bot/merter_dca_state.json"))
for yuva, p in (state.get("positions") or {}).items():
    if p and p.get("symbol") == "ZROUSDT":
        print(yuva, json.dumps(p, indent=2))

print("\n=== merter_dca.log ZRO (son 25) ===")
lines = open(f"{ROOT}/signal_bot/merter_dca.log", encoding="utf-8", errors="replace").readlines()
zro = [l.rstrip() for l in lines if "ZRO" in l.upper()]
for l in zro[-25:]:
    print(l)

print("\n=== mina_bot.log ZRO (son 20) ===")
lines2 = open(f"{ROOT}/mina_bot.log", encoding="utf-8", errors="replace").readlines()
zro2 = [l.rstrip() for l in lines2 if "ZRO" in l.upper()]
for l in zro2[-20:]:
    print(l)

print("\n=== signals_log ZRO ===")
sl = open(f"{ROOT}/signal_bot/signals_log.txt", encoding="utf-8", errors="replace").readlines()
for l in sl:
    if "ZRO" in l.upper():
        print(l.rstrip()[:200])

print("\n=== Binance ZROUSDT ===")
from backend.config import BinanceConfig
client = BinanceConfig().get_client()
for p in client.futures_position_information(symbol="ZROUSDT"):
    if float(p["positionAmt"]) != 0:
        print({k: p[k] for k in ("symbol", "positionAmt", "entryPrice", "markPrice", "leverage", "isolatedMargin", "unRealizedProfit")})

conn.close()
