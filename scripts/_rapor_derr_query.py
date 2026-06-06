#!/usr/bin/env python3
import sqlite3
DB = "/root/MINA_v2/mina_trading_journal.db"

def q(sql):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        return cur.execute(sql).fetchall()
    finally:
        con.close()

print("=" * 80)
print("2) DERR — bugün kapanan işlemler")
print("=" * 80)
rows = q("""
SELECT symbol, side, close_reason, pnl_usdt, close_time
FROM trades
WHERE date(close_time)='2026-06-04'
""")
if not rows:
    print("(kayıt yok)")
else:
    cols = ["symbol", "side", "close_reason", "pnl_usdt", "close_time"]
    print("  ".join(f"{c:>14}" for c in cols))
    for r in rows:
        print("  ".join(f"{str(r[c] or ''):>14}" for c in cols))

print()
print("=" * 80)
print("4) signal_decisions — bugün onaylanan (k2 != REJECT)")
print("=" * 80)
try:
    rows2 = q("""
    SELECT source, symbol, k2_label, k3_action, created_at
    FROM signal_decisions
    WHERE date(created_at)='2026-06-04' AND k2_label != 'REJECT'
    """)
except Exception as e:
    print(f"(sorgu hatası — source/symbol kolonu yok: {e})")
    print()
    print("Alternatif (merter_symbol):")
    rows2 = q("""
    SELECT scenario_label, merter_symbol, k2_label, k3_action, created_at
    FROM signal_decisions
    WHERE date(created_at)='2026-06-04' AND k2_label != 'REJECT'
    """)
    cols = ["scenario_label", "merter_symbol", "k2_label", "k3_action", "created_at"]
    if not rows2:
        print("(kayıt yok)")
    else:
        print("  ".join(f"{c:>16}" for c in cols))
        for r in rows2:
            print("  ".join(f"{str(r[c] or ''):>16}" for c in cols))
    rows2 = None
if rows2 is not None:
    if not rows2:
        print("(kayıt yok)")
    else:
        cols = ["source", "symbol", "k2_label", "k3_action", "created_at"]
        print("  ".join(f"{c:>14}" for c in cols))
        for r in rows2:
            print("  ".join(f"{str(r[c] or ''):>14}" for c in cols))
