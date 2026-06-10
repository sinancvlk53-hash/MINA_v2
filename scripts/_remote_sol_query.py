#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import connect_paramiko
import paramiko

JOURNAL = r"""cd /root/MINA_v2 && python3 << 'PYEOF'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[0] for d in conn.execute('PRAGMA table_info(trades)').fetchall()]
rows = conn.execute("SELECT * FROM trades WHERE symbol='SOLUSDT' ORDER BY open_time DESC LIMIT 2").fetchall()
for r in rows:
    for c, v in zip(cols, r):
        print(f'{c}: {v}')
    print('---')
conn.close()
PYEOF"""

BINANCE = r"""cd /root/MINA_v2 && source venv/bin/activate && python3 << 'PYEOF'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
orders = [o for o in client.futures_get_open_orders() if 'SOL' in o['symbol']]
print(f'SOL emir: {len(orders)}')
for o in orders:
    print(o['symbol'], o['side'], o['price'], o['type'])
PYEOF"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
for label, cmd in [("JOURNAL", JOURNAL), ("BINANCE", BINANCE)]:
    print(f"=== {label} ===")
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("ERR:", err)
c.close()
