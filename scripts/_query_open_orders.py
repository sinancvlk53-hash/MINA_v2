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
orders = client.futures_get_open_orders()
print(f'Bekleyen emir: {len(orders)}')
for o in orders:
    print(o['symbol'], o['side'], o['type'], o['price'], o['origQty'], o['status'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, stderr = c.exec_command(REMOTE, timeout=60)
sys.stdout.buffer.write(stdout.read())
err = stderr.read().decode('utf-8', errors='replace')
if err.strip():
    sys.stdout.buffer.write(('\nSTDERR: ' + err).encode('utf-8', errors='replace'))
c.close()
