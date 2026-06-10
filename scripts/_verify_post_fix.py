#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

REMOTE = r"""
echo "=== ht-listener status ==="
systemctl status mina-ht-listener --no-pager | head -15
echo ""
echo "=== lock ==="
cat /root/MINA_v2/signal_bot/ht_listener.lock 2>/dev/null || echo "(yok)"
echo ""
echo "=== SOL journal (son 2) ==="
cd /root/MINA_v2 && python3 << 'PY'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[0] for d in conn.execute('PRAGMA table_info(trades)').fetchall()]
rows = conn.execute("SELECT * FROM trades WHERE symbol='SOLUSDT' ORDER BY open_time DESC LIMIT 2").fetchall()
for r in rows:
    for c,v in zip(cols,r):
        if c in ('defense_triggered','defense_prices','weighted_avg_price','status','open_time','close_time','pnl_usdt'):
            print(f'{c}: {v}')
    print('---')
conn.close()
PY
echo ""
echo "=== Acik pozisyonlar Binance ==="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
import os
from dotenv import load_dotenv
load_dotenv()
from binance.client import Client
c = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
for p in c.futures_position_information():
    amt = float(p['positionAmt'])
    if amt != 0:
        print(p['symbol'], p['positionSide'], amt)
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=60)
sys.stdout.buffer.write(stdout.read())
c.close()
