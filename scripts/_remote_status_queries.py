#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
echo "========== 1. approval_bot servisi =========="
systemctl status mina-approval-bot 2>/dev/null | head -15 || echo "(systemd servisi yok)"
echo ""
ps aux | grep approval_bot | grep -v grep || echo "(process yok)"

echo ""
echo "========== 2. ht_signals_queue.json =========="
python3 -m json.tool /root/MINA_v2/signal_bot/ht_signals_queue.json 2>/dev/null || echo "DOSYA YOK"

echo ""
echo "========== 3. Binance acik pozisyonlar =========="
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
    print(p['symbol'], p['positionAmt'], p['unrealizedProfit'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=120)
sys.stdout.buffer.write(stdout.read())
c.close()
