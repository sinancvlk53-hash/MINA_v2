#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
rm -f /root/MINA_v2/signal_bot/approval_bot.lock
systemctl restart mina-approval-bot
sleep 2
systemctl status mina-approval-bot --no-pager | head -12
echo ""
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
print(f'Acik: {len(positions)}')
for p in positions:
    side = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    print(p['symbol'], side, p['positionAmt'], 'PnL:', p['unrealizedProfit'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=60)
sys.stdout.buffer.write(stdout.read())
c.close()
