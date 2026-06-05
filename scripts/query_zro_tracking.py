#!/usr/bin/env python3
import json
ROOT="/root/MINA_v2"
for fn in ["initial_prices.json","initial_margins.json","tp_levels.json","defense_levels.json"]:
    p=f"{ROOT}/{fn}"
    try:
        d=json.load(open(p))
        z={k:v for k,v in d.items() if "ZRO" in k}
        if z: print(fn, z)
    except Exception as e:
        print(fn, e)
print("=== journal grep 06:31 ===")
import sqlite3
c=sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
print(c.execute("SELECT * FROM trades WHERE id=26").fetchone())
print("=== log lines 06:31 ===")
for l in open(f"{ROOT}/mina_bot.log",encoding="utf-8",errors="replace"):
    if "2026-06-05 06:31" in l or "2026-06-05 06:30" in l:
        print(l.rstrip())
