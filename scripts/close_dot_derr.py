#!/usr/bin/env python3
import os, sys
ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from config import BinanceConfig
from mina_trading_journal import TradingJournal

c = BinanceConfig().get_client()
pos = [p for p in c.futures_position_information() if p["symbol"] == "DOTUSDT" and float(p.get("positionAmt") or 0) != 0]
print("DOT binance:", len(pos))

j = TradingJournal(os.path.join(ROOT, "mina_trading_journal.db"))
cur = j.conn.cursor()
row = cur.execute("SELECT * FROM trades WHERE id=34").fetchone()
print("DERR id=34 status:", row["status"], "qty:", row["open_qty"])

if not pos and row and row["status"] == "open":
    try:
        close_px = float(c.futures_mark_price(symbol="DOTUSDT")["markPrice"])
    except Exception:
        close_px = float(row["open_price"])
    entry = float(row["open_price"])
    qty = float(row["open_qty"])
    pnl_usdt = (entry - close_px) * qty
    margin = float(row["initial_margin"] or 1)
    roe = (pnl_usdt / margin * 100) if margin else 0
    pnl_pct = (pnl_usdt / (entry * qty) * 100) if entry * qty else 0
    j.log_trade_close(34, close_px, qty, "Trailing/Reconcile", pnl_usdt, pnl_pct, roe)
    print(f"OK DERR id=34 closed px={close_px} pnl={pnl_usdt:.4f}")

rows = cur.execute("SELECT id,symbol,side,open_qty FROM trades WHERE status='open'").fetchall()
print("DERR open:", [dict(r) for r in rows])
j.close()
