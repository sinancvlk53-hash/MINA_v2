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
import os, sys, json
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

print('========== 1. Orphan Merter iptal ==========')
state_paths = [
    '/root/MINA_v2/signal_bot/merter_dca_state.json',
    '/root/MINA_v2/merter_dca_state.json',
]
state = {}
for p in state_paths:
    try:
        with open(p) as f:
            state = json.load(f)
        print(f'State dosyasi: {p}')
        break
    except FileNotFoundError:
        continue
print('State:', json.dumps(state, indent=2))

orphan_coins = ['MINAUSDT', 'ADAUSDT', 'CRVUSDT', 'MEMEUSDT']
for coin in orphan_coins:
    before = [o for o in client.futures_get_open_orders(symbol=coin)]
    print(f'{coin} acik emir (once): {len(before)}')
    try:
        client.futures_cancel_all_open_orders(symbol=coin)
        print(f'{coin} emirleri iptal edildi')
    except Exception as e:
        print(f'{coin} hata: {e}')

print('')
print('========== 2. LINK duplicate iptal ==========')
orders = [o for o in client.futures_get_open_orders() if o['symbol'] == 'LINKUSDT']
print(f'LINK emirleri: {len(orders)}')
for o in orders:
    print(o['orderId'], o['side'], o['price'], o['type'])
    client.futures_cancel_order(symbol='LINKUSDT', orderId=o['orderId'])
    print('iptal edildi')

print('')
print('========== 3. Sonuc kontrol ==========')
orders = client.futures_get_open_orders()
print(f'Kalan emir: {len(orders)}')
for o in orders:
    print(o['symbol'], o['side'], o['price'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, stderr = c.exec_command(REMOTE, timeout=120)
sys.stdout.buffer.write(stdout.read())
err = stderr.read().decode('utf-8', errors='replace')
if err.strip():
    sys.stdout.buffer.write(('\nSTDERR: ' + err).encode('utf-8', errors='replace'))
c.close()
