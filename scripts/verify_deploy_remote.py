#!/usr/bin/env python3
"""Sunucuda trade_id + makro doğrulama."""
import os
import sqlite3
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)

trade_id = int(sys.argv[1]) if len(sys.argv) > 1 else 20

db = os.path.join(ROOT, "mina_trading_journal.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute(
    "SELECT id, symbol, side, leverage, open_time, signal_source FROM trades WHERE id=?",
    (trade_id,),
)
row = cur.fetchone()
print("TRADE", dict(row) if row else f"id={trade_id} yok")
conn.close()

from dashboard.dashboard_ws import get_macro_levels

levels = get_macro_levels()
total = next((x for x in levels if x.get("coin") == "TOTAL"), None)
if total:
    snip = (total.get("snippet") or total.get("text") or "")[:150]
    print("MACRO TOTAL snippet:", snip or "(boş)")
else:
    print("MACRO TOTAL: missing")
