#!/usr/bin/env python3
import os, sys, json, sqlite3
ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from config import BinanceConfig, AccountManager

cfg = BinanceConfig()
c = cfg.get_client()
acc = AccountManager(c)
print("=== BAKIYE ===")
print("USDT balance field:", acc.get_usdt_balance())
acct = c.futures_account()
print("totalWalletBalance:", acct.get("totalWalletBalance"))
print("availableBalance:", acct.get("availableBalance"))

print("\n=== BINANCE POZISYONLAR ===")
pos = [p for p in c.futures_position_information() if float(p.get("positionAmt") or 0) != 0]
print("acik:", len(pos))
total_margin = 0
for p in sorted(pos, key=lambda x: x["symbol"]):
    amt = float(p["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    m = float(p.get("isolatedMargin") or 0)
    total_margin += m
    print(f"  {p['symbol']} {side} amt={abs(amt)} entry={p.get('entryPrice')} margin={m} lev={p.get('leverage')}")
print("toplam isolated margin:", round(total_margin, 2))

print("\n=== DERR ===")
conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id,symbol,side,leverage,open_price,open_qty,initial_margin,signal_source FROM trades WHERE status='open' ORDER BY id"
).fetchall()
print("acik kayit:", len(rows))
for r in rows:
    print(dict(r))
conn.close()
