#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sqlite3
from datetime import datetime, timezone

ROOT = "/root/MINA_v2"

print("=== mina_bot ZRO open/entry/giriş 2026-06-05 ===")
lines = open(f"{ROOT}/mina_bot.log", encoding="utf-8", errors="replace").readlines()
for l in lines:
    if "ZRO" not in l.upper():
        continue
    if "2026-06-05" not in l:
        continue
    if any(x in l.lower() for x in ("open", "entry", "giriş", "market", "long", "slot", "bridge", "signal", "pozisyon")):
        print(l.rstrip())

print("\n=== mina_bot ZRO ALL 2026-06-05 06:2x-06:4x ===")
for l in lines:
    if "ZRO" in l.upper() and "2026-06-05 06:3" in l:
        print(l.rstrip())

print("\n=== DERR open trades (any symbol open) ===")
conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
for r in conn.execute("SELECT id,symbol,side,open_time,signal_source,status FROM trades WHERE status='open'").fetchall():
    print(dict(r))

print("\n=== DERR ALL open/close ZRO journal lines in signals ===")
for r in conn.execute("SELECT id,open_time,close_time,status,signal_source,open_price FROM trades WHERE symbol='ZROUSDT'").fetchall():
    print(dict(r))

print("\n=== position_sources full ===")
import json
ps = json.load(open(f"{ROOT}/position_sources.json"))
print(json.dumps(ps, indent=2))

print("\n=== Binance userTrades ZRO (last 30) ===")
import sys
sys.path.insert(0, ROOT)
from backend.config import BinanceConfig
client = BinanceConfig().get_client()
trades = client.futures_account_trades(symbol="ZROUSDT", limit=30)
for t in reversed(trades):
    ts = datetime.fromtimestamp(t["time"]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {t['side']} qty={t['qty']} price={t['price']} realized={t.get('realizedPnl')} id={t['id']}")

print("\n=== Open orders ZRO ===")
for o in client.futures_get_open_orders(symbol="ZROUSDT"):
    print({k: o[k] for k in ("orderId","type","side","price","origQty","status","time")})

conn.close()
