#!/usr/bin/env python3
import os, sqlite3, sys
sys.path.insert(0, '/root/MINA_v2')
sys.path.insert(0, '/root/MINA_v2/backend')
from dotenv import load_dotenv
load_dotenv('/root/MINA_v2/.env')
from config import BinanceConfig

cfg = BinanceConfig()
client = cfg.get_client()
print('=' * 90)
print('BINANCE TESTNET (SUNUCU) — ACIK POZISYONLAR')
print('=' * 90)
positions = client.futures_position_information()
open_pos = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
if not open_pos:
    print('(acik pozisyon yok)')
else:
    print('Sembol           Yon    Giris          Mark       PnL (USDT)    ROE %')
    print('-' * 72)
    for p in open_pos:
        amt = float(p['positionAmt'])
        side = 'LONG' if amt > 0 else 'SHORT'
        entry = float(p.get('entryPrice') or 0)
        mark = float(p.get('markPrice') or 0)
        pnl = float(p.get('unRealizedProfit') or 0)
        margin = float(p.get('isolatedMargin') or p.get('initialMargin') or 0)
        if margin <= 0:
            margin = abs(amt * entry) / max(float(p.get('leverage') or 1), 1)
        roe = pnl / margin * 100 if margin > 0 else 0
        print(f"{p['symbol']:<16} {side:<6} {entry:>12.6f} {mark:>12.6f} {pnl:>+12.4f} {roe:>+7.2f}")
print()
print('=' * 90)
print("DERR — BUGUN KAPANAN ISLEMLER (2026-06-03)")
print('=' * 90)
conn = sqlite3.connect('/root/MINA_v2/mina_trading_journal.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT symbol, side, close_reason, pnl_usdt, close_time
    FROM trades
    WHERE status='closed' AND date(created_at)='2026-06-03'
    ORDER BY close_time DESC
""")
rows = cur.fetchall()
if not rows:
    print('(kayit yok)')
else:
    print('Sembol           Yon    Kapanis Nedeni         PnL USDT   close_time')
    print('-' * 80)
    for r in rows:
        pnl = r['pnl_usdt']
        pnl_s = f"{pnl:+.4f}" if pnl is not None else 'N/A'
        print(f"{r['symbol']:<16} {r['side']:<6} {(r['close_reason'] or ''):<22} {pnl_s:>10} {(r['close_time'] or '')}")
    print(f"\nToplam: {len(rows)} islem")
conn.close()
