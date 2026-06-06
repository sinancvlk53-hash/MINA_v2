#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""12h report 2026-06-05 20:00 UTC -> 2026-06-06 08:00 UTC"""
import os
import sqlite3
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from config import BinanceConfig, AccountManager

LOG_PAT = ("take_profit", "trailing_stop", "defense", "stop_loss", "hard_stop", "açıldı", "kapandı")
TIME_PAT = ("2026-06-05 2", "2026-06-06 0")


def section(title):
    print("=" * 80)
    print(title)
    print("=" * 80)


section("1) mina_bot.log")
log_path = os.path.join(ROOT, "mina_bot.log")
if os.path.isfile(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not any(p in line for p in LOG_PAT):
                continue
            if not any(t in line for t in TIME_PAT):
                continue
            print(line.rstrip())
else:
    print("(dosya yok)")

print()
section("2) DERR kapanan (close_time >= 2026-06-05 20:00)")
conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT symbol, side, leverage, open_price, close_price, close_reason, pnl_usdt,
           open_time, close_time, signal_source
    FROM trades WHERE close_time >= '2026-06-05 20:00' ORDER BY close_time
    """
).fetchall()
if not rows:
    print("(kayıt yok)")
else:
    for r in rows:
        print(dict(r))

print()
section("3) DERR acik")
rows = conn.execute(
    """
    SELECT symbol, side, leverage, open_price, signal_source, open_time
    FROM trades WHERE status='open' ORDER BY open_time
    """
).fetchall()
if not rows:
    print("(kayıt yok)")
else:
    for r in rows:
        print(dict(r))

print()
section("4) merter_dca.log")
mdca = os.path.join(ROOT, "signal_bot", "merter_dca.log")
if os.path.isfile(mdca):
    found = False
    with open(mdca, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "2026-06-05T2" in line or "2026-06-06T0" in line:
                print(line.rstrip())
                found = True
    if not found:
        print("(eşleşme yok)")
else:
    print("(dosya yok)")

print()
section("5) signals_log.txt — tail 30 (20-29 / 00-09)")
sig = os.path.join(ROOT, "signal_bot", "signals_log.txt")
if os.path.isfile(sig):
    matched = []
    with open(sig, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "2026-06-05 2" in line or "2026-06-06 0" in line:
                matched.append(line.rstrip())
    for line in matched[-30:]:
        print(line)
    if not matched:
        print("(eşleşme yok)")
else:
    print("(dosya yok)")

print()
section("6) Binance acik pozisyonlar")
client = BinanceConfig().get_client()
open_pos = [p for p in client.futures_position_information() if float(p.get("positionAmt") or 0) != 0]
print(f"acik_sayisi: {len(open_pos)}\n")
for p in sorted(open_pos, key=lambda x: x["symbol"]):
    print("--- RAW ---")
    for k in sorted(p.keys()):
        print(f"  {k}: {p[k]}")
    print()

print("--- TABLO ---")
print(f"{'Sembol':<12} {'Yon':<6} {'Lev':>4} {'Entry':>14} {'Mark':>14} {'PnL':>12} {'ROE%':>8} {'Marjin':>12}")
print("-" * 88)
total_upnl = total_margin = 0.0
for p in sorted(open_pos, key=lambda x: x["symbol"]):
    amt = float(p["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    upnl = float(p.get("unRealizedProfit") or 0)
    lev = int(float(p.get("leverage") or 1))
    m = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
    if m <= 0 and entry > 0:
        m = abs(amt) * entry / max(lev, 1)
    roe = (upnl / m * 100) if m > 0 else 0.0
    total_upnl += upnl
    total_margin += m
    print(
        f"{p['symbol']:<12} {side:<6} {lev:>4}x {entry:>14.6f} {mark:>14.6f} "
        f"{upnl:>+12.4f} {roe:>+7.2f}% {m:>12.4f}"
    )
print("-" * 88)
print(f"TOPLAM unrealized PnL: {total_upnl:+.4f} USDT")
print(f"TOPLAM isolated marjin: {total_margin:.4f} USDT")

print()
section("7) Kasa durumu")
acc = AccountManager(client)
balance = acc.get_usdt_balance()
try:
    acct = client.futures_account()
    print(f"USDT balance (AccountManager): {balance:.4f}")
    print(f"totalWalletBalance: {float(acct.get('totalWalletBalance') or balance):.4f}")
    print(f"availableBalance: {float(acct.get('availableBalance') or 0):.4f}")
except Exception as e:
    print(f"USDT balance: {balance:.4f}")
    print(f"futures_account err: {e}")

row = conn.execute(
    "SELECT COUNT(*) n, COALESCE(SUM(pnl_usdt),0) s FROM trades WHERE close_time >= '2026-06-05 20:00:00'"
).fetchone()
print(f"unrealized PnL toplam: {total_upnl:+.4f} USDT")
print(f"DERR kapanan (>= 2026-06-05 20:00): {row[0]} islem")
print(f"realized PnL son 12h (DERR): {float(row[1]):+.4f} USDT")
conn.close()
