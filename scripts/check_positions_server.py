#!/usr/bin/env python3
import os, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", "root", password=os.environ.get("MINA_SSH_PASS", "REDACTED"), timeout=20)
cmd = r'''cd /root/MINA_v2 && venv/bin/python -c "
import os
from binance.client import Client
from dotenv import load_dotenv
load_dotenv()
Client.ping = lambda self: {}
c = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
bal = [x for x in c.futures_account_balance() if x['asset']=='USDT'][0]
print('BALANCE', bal['balance'])
for p in c.futures_position_information():
    amt=float(p.get('positionAmt',0))
    if amt!=0:
        print('OPEN', p['symbol'], 'LONG' if amt>0 else 'SHORT', 'amt', amt, 'margin', p.get('isolatedMargin'))
"'''
_, o, _ = c.exec_command(cmd, timeout=60)
print(o.read().decode())
c.close()
