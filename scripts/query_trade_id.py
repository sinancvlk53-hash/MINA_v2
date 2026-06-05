#!/usr/bin/env python3
"""DERR/journal trade_id sorgusu (sunucu)."""
import os
import sqlite3
import sys

ROOT = os.environ.get("MINA_ROOT", "/root/MINA_v2")
DB = os.path.join(ROOT, "mina_trading_journal.db")
TRADE_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 20

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute(
    "SELECT id, symbol, side, leverage, open_time, open_price, signal_source FROM trades WHERE id=?",
    (TRADE_ID,),
)
row = cur.fetchone()
if row:
    print(dict(row))
else:
    print(f"trade_id={TRADE_ID} bulunamadı")
conn.close()
