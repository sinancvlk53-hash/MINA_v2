#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

orders = [o for o in client.futures_get_open_orders() if o['symbol'] == 'ZECUSDT' and o['side'] == 'BUY']
print(f'ZEC BUY emir: {len(orders)}')
for o in orders:
    client.futures_cancel_order(symbol='ZECUSDT', orderId=o['orderId'])
    print(f'iptal: {o["orderId"]} @ {o["price"]}')

remaining = client.futures_get_open_orders()
print(f'Kalan toplam emir: {len(remaining)}')
for o in remaining:
    print(o['symbol'], o['side'], o['price'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=60)
sys.stdout.buffer.write(stdout.read())
c.close()
