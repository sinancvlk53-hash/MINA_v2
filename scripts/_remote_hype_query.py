#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && source venv/bin/activate && python3 << 'PYEOF'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

price = client.futures_symbol_ticker(symbol='HYPEUSDT')
print(f'HYPE şu an: {price["price"]}')

positions = [p for p in client.futures_position_information() if p['symbol'] == 'HYPEUSDT' and float(p['positionAmt']) != 0]
if not positions:
    print('Pozisyon: yok')
for p in positions:
    print(f'Pozisyon: {p["positionAmt"]} @ {p["entryPrice"]}')
PYEOF"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=60)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
report = (out or "") + ("\nERR:\n" + err if err.strip() else "")
sys.stdout.buffer.write(report.encode("utf-8", errors="replace"))
c.close()
