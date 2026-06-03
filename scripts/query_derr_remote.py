#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "DERR_DB", "/root/MINA_v2/mina_trading_journal.db"
)
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def dump(title, sql):
    print(title)
    cur.execute(sql)
    rows = cur.fetchall()
    if not rows:
        print("(no rows)")
        print()
        return
    cols = rows[0].keys()
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(r[c]) if r[c] is not None else "" for c in cols))
    print()


print("=== SELECT name FROM sqlite_master WHERE type='table' ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    print(t)
print()

for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"=== SELECT COUNT(*) FROM {t} ===")
    print(cnt)
    print()

dump(
    "=== SELECT symbol, side, status, close_reason, pnl_usdt, created_at FROM trades WHERE status='closed' AND date(created_at)='2026-06-03' ORDER BY created_at DESC ===",
    "SELECT symbol, side, status, close_reason, pnl_usdt, created_at FROM trades WHERE status='closed' AND date(created_at)='2026-06-03' ORDER BY created_at DESC",
)

dump(
    "=== SELECT k2_label, COUNT(*) FROM signal_decisions GROUP BY k2_label ===",
    "SELECT k2_label, COUNT(*) FROM signal_decisions GROUP BY k2_label",
)

dump(
    "=== SELECT COUNT(*) AS total_closed FROM trades WHERE status='closed' ===",
    "SELECT COUNT(*) AS total_closed FROM trades WHERE status='closed'",
)

dump(
    "=== SELECT SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) AS winners FROM trades WHERE status='closed' ===",
    "SELECT SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) AS winners FROM trades WHERE status='closed'",
)

dump(
    "=== SELECT SUM(CASE WHEN pnl_usdt < 0 THEN 1 ELSE 0 END) AS losers FROM trades WHERE status='closed' ===",
    "SELECT SUM(CASE WHEN pnl_usdt < 0 THEN 1 ELSE 0 END) AS losers FROM trades WHERE status='closed'",
)

dump(
    "=== SELECT SUM(CASE WHEN pnl_usdt = 0 OR pnl_usdt IS NULL THEN 1 ELSE 0 END) AS breakeven_or_null FROM trades WHERE status='closed' ===",
    "SELECT SUM(CASE WHEN pnl_usdt = 0 OR pnl_usdt IS NULL THEN 1 ELSE 0 END) AS breakeven_or_null FROM trades WHERE status='closed'",
)

dump(
    "=== SELECT ROUND(AVG(pnl_usdt), 4) AS avg_pnl_usdt FROM trades WHERE status='closed' ===",
    "SELECT ROUND(AVG(pnl_usdt), 4) AS avg_pnl_usdt FROM trades WHERE status='closed'",
)

dump(
    "=== SELECT ROUND(100.0 * SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate_pct FROM trades WHERE status='closed' ===",
    "SELECT ROUND(100.0 * SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate_pct FROM trades WHERE status='closed'",
)

conn.close()
