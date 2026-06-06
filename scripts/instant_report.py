#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anlık durum: Binance pozisyonlar + bugün DERR kapanış + mina_bot.log tail."""
import os
import sys
import sqlite3
from datetime import datetime, date

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from config import BinanceConfig

client = BinanceConfig().get_client()
raw = client.futures_position_information()
open_pos = [p for p in raw if float(p.get("positionAmt") or 0) != 0]

print("=" * 72)
print("BINANCE TESTNET — AÇIK POZİSYONLAR")
print("=" * 72)
print(f"Tarih: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

if not open_pos:
    print("(açık pozisyon yok)\n")
else:
    print(f"{'Sembol':<12} {'Yön':<6} {'Lev':>4} {'Entry':>14} {'Mark':>14} {'PnL USDT':>12} {'ROE%':>8}")
    print("-" * 72)
    total_upnl = 0.0
    for p in sorted(open_pos, key=lambda x: x["symbol"]):
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        entry = float(p.get("entryPrice") or 0)
        mark = float(p.get("markPrice") or 0)
        upnl = float(p.get("unRealizedProfit") or 0)
        lev = int(float(p.get("leverage") or 1))
        iso = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
        if iso <= 0 and entry > 0:
            iso = abs(amt) * entry / max(lev, 1)
        roe = (upnl / iso * 100) if iso > 0 else 0.0
        total_upnl += upnl
        print(
            f"{p['symbol']:<12} {side:<6} {lev:>4}x "
            f"{entry:>14.6f} {mark:>14.6f} {upnl:>+12.4f} {roe:>+7.2f}%"
        )
    print("-" * 72)
    print(f"Toplam açık: {len(open_pos)}  |  Toplam unrealized PnL: {total_upnl:+.4f} USDT\n")

print("=" * 72)
print("DERR — BUGÜN KAPANAN İŞLEMLER")
print("=" * 72)
today = date.today().isoformat()
conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT id, symbol, side, leverage, open_time, close_time, close_reason,
           pnl_usdt, roe_percent, signal_source
    FROM trades
    WHERE status = 'closed' AND date(close_time) = date('now', 'localtime')
    ORDER BY close_time DESC
    """
).fetchall()
if not rows:
    rows = conn.execute(
        """
        SELECT id, symbol, side, leverage, open_time, close_time, close_reason,
               pnl_usdt, roe_percent, signal_source
        FROM trades
        WHERE status = 'closed' AND close_time >= ?
        ORDER BY close_time DESC
        """,
        (today + " 00:00:00",),
    ).fetchall()

if not rows:
    print(f"Bugün ({today}) kapanan işlem yok.\n")
else:
    for r in rows:
        print(
            f"  id={r['id']} {r['symbol']} {r['side']} {r['leverage']}x "
            f"close={r['close_time']} reason={r['close_reason']} "
            f"pnl={r['pnl_usdt']:+.4f} USDT roe={r['roe_percent']}% src={r['signal_source']}"
        )
    total = sum(float(r["pnl_usdt"] or 0) for r in rows)
    print(f"\nBugün kapanan: {len(rows)}  |  Realized PnL: {total:+.4f} USDT\n")
conn.close()

print("=" * 72)
print("mina_bot.log — SON 20 SATIR")
print("=" * 72)
log = os.path.join(ROOT, "mina_bot.log")
if os.path.isfile(log):
    with open(log, encoding="utf-8", errors="replace") as f:
        for line in f.readlines()[-20:]:
            print(line.rstrip())
else:
    print("(log dosyası yok)")
