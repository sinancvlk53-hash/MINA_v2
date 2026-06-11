#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMDS = [
("6. ht_signals_queue.json", "cat /root/MINA_v2/signal_bot/ht_signals_queue.json 2>/dev/null | python3 -m json.tool || echo '(yok)'"),
("7. ht_pdf_basari_orani", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[1] for d in conn.execute('PRAGMA table_info(ht_pdf_basari_orani)').fetchall()]
rows = conn.execute('SELECT * FROM ht_pdf_basari_orani ORDER BY created_at DESC LIMIT 10').fetchall()
print('KOLONLAR:', cols)
for r in rows:
    for c,v in zip(cols,r): print(f'{c}: {v}')
    print('---')
conn.close()
" """),
("8. Binance", r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
orders = client.futures_get_open_orders()
print(f'Açık pozisyon: {len(positions)}')
for p in positions: print(p['symbol'], p['positionAmt'], p['entryPrice'])
print(f'Bekleyen emir: {len(orders)}')
for o in orders: print(o['symbol'], o['side'], o['price'], o['type'])
" """),
("9a. mina_bot.log", r"grep -i 'pdf\|visual\|signal\|sinyal\|error\|hata' /root/MINA_v2/mina_bot.log 2>/dev/null | tail -50 || echo '(yok)'"),
("9b. mina-pdf-listener", "journalctl -u mina-pdf-listener -n 30 --no-pager 2>&1"),
("9c. mina-approval-bot", "journalctl -u mina-approval-bot -n 30 --no-pager 2>&1"),
("9d. mina-ht-listener", "journalctl -u mina-ht-listener -n 30 --no-pager 2>&1"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
for title, cmd in CMDS:
    print("="*60, title, "="*60, sep="\n")
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip(): print("ERR:", err)
c.close()
