#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMDS = [
("1. ht_signals_queue.json", "cat /root/MINA_v2/signal_bot/ht_signals_queue.json 2>/dev/null | python3 -m json.tool || echo 'BOŞ VEYA YOK'"),
("2. ht_pdf_basari_orani AKT/CFG/QQQ", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
rows = conn.execute('''
    SELECT id, symbol, direction, entry_price, tp_price, stop_price, 
           source, status, created_at
    FROM ht_pdf_basari_orani 
    WHERE symbol LIKE '%AKT%' OR symbol LIKE '%CFG%' OR symbol LIKE '%QQQ%'
    ORDER BY created_at DESC
''').fetchall()
print(f'Kayıt sayısı: {len(rows)}')
for r in rows: print(r)
conn.close()
" """),
("3. mina-ht-listener logs", "journalctl -u mina-ht-listener -n 30 --no-pager 2>&1"),
("4. Binance AKT/CFG/QQQ", r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
for coin in ['AKTUSDT', 'CFGUSDT', 'QQQUSDT']:
    try:
        orders = [o for o in client.futures_get_open_orders() if o['symbol'] == coin]
        pos = [p for p in client.futures_position_information() if p['symbol'] == coin and float(p['positionAmt']) != 0]
        print(f'{coin}: {len(orders)} emir, {len(pos)} pozisyon')
        for o in orders: print('  emir', o['side'], o['price'], o['type'])
        for p in pos: print('  poz', p['positionAmt'], p['entryPrice'])
    except Exception as e:
        print(f'{coin}: {e}')
" """),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
for title, cmd in CMDS:
    print("=" * 60)
    print(title)
    print("=" * 60)
    _, o, e = c.exec_command(cmd, timeout=120)
    sys.stdout.buffer.write(o.read())
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
    print()
c.close()
