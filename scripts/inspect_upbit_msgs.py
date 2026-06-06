#!/usr/bin/env python3
import sqlite3
import json
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mina_trading_journal.db")
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
rows = c.execute(
    """
    SELECT timestamp, coins_mentioned, raw_text
    FROM haluk_messages
    WHERE lower(raw_text) LIKE '%upbit%'
       OR lower(raw_text) LIKE '%listing%'
       OR lower(raw_text) LIKE '%listeleme%'
    ORDER BY timestamp DESC
    """
).fetchall()
for r in rows:
    print(r["timestamp"], r["coins_mentioned"], (r["raw_text"] or "")[:100].replace("\n", " "))
