#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko
cmd = r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
orders = client.futures_get_open_orders()
print(f'Açık pozisyon: {len(positions)}')
for p in positions:
    upnl = p.get('unRealizedProfit') or p.get('unrealizedProfit') or '?'
    print(p['symbol'], p['positionAmt'], p['entryPrice'], upnl)
print(f'Bekleyen emir: {len(orders)}')
for o in orders: print(o['symbol'], o['side'], o['price'], o['type'])
" """
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(cmd, timeout=90)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode()
if err.strip(): print("ERR:", err)
c.close()
