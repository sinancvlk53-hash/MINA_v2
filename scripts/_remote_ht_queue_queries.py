#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
echo "========== 1. ht_signals_queue.json =========="
if [ -f /root/MINA_v2/signal_bot/ht_signals_queue.json ]; then
  python3 -m json.tool /root/MINA_v2/signal_bot/ht_signals_queue.json
else
  echo "DOSYA YOK"
fi

echo ""
echo "========== 2. signal_slot_bridge.py =========="
grep -n "haluk_pdf\|ht_pdf\|HT_PDF\|try_open_haluk" /root/MINA_v2/signal_bot/signal_slot_bridge.py 2>/dev/null | head -20 || echo "(eslesme yok)"

echo ""
echo "========== 3. queue_watcher.py =========="
grep -n "haluk\|ht_pdf\|source" /root/MINA_v2/signal_bot/queue_watcher.py 2>/dev/null | head -20 || echo "(dosya yok veya eslesme yok)"

echo ""
echo "========== 4. Binance acik pozisyonlar =========="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
print(f'Acik pozisyon: {len(positions)}')
for p in positions:
    print(p['symbol'], p['positionAmt'], p['unrealizedProfit'])
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, stderr = c.exec_command(REMOTE, timeout=120)
sys.stdout.buffer.write(stdout.read())
err = stderr.read().decode('utf-8', errors='replace')
if err.strip():
    sys.stdout.buffer.write(b'\nSTDERR:\n')
    sys.stdout.buffer.write(err.encode('utf-8', errors='replace'))
c.close()
