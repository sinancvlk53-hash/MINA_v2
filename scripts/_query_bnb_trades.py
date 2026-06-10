#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
cd /root/MINA_v2 && python3 << 'PY'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[0] for d in conn.execute('PRAGMA table_info(trades)').fetchall()]
rows = conn.execute("SELECT * FROM trades WHERE symbol='BNBUSDT' ORDER BY open_time DESC LIMIT 2").fetchall()
for r in rows:
    for c, v in zip(cols, r):
        print(f'{c}: {v}')
    print('---')
conn.close()
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
