#!/usr/bin/env python3
import sqlite3
c = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
rows = c.execute(
    "SELECT id,symbol,side,leverage,status,defense_triggered,open_price FROM trades WHERE symbol='FHEUSDT' ORDER BY id DESC LIMIT 5"
).fetchall()
for r in rows:
    print(r)
