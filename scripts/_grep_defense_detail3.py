#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, sys, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=25)

script = r'''
import sqlite3, json
conn = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print("=== trades schema ===")
for r in cur.execute("PRAGMA table_info(trades)"):
    print(r["name"], r["type"])
print()
print("=== BCH BNB trades ===")
for r in cur.execute("SELECT id,symbol,side,leverage,defense_triggered,defense_prices,status,created_at,close_time,pnl_usdt FROM trades WHERE symbol IN ('BCHUSDT','BNBUSDT') ORDER BY id DESC LIMIT 8"):
    print(dict(r))
print()
print("=== XRP AVAX today ===")
for r in cur.execute("SELECT id,symbol,side,leverage,status,close_reason,pnl_usdt,created_at,close_time FROM trades WHERE symbol IN ('XRPUSDT','AVAXUSDT') AND date(created_at)='2026-06-03' ORDER BY close_time DESC"):
    print(dict(r))
print()
print("=== initial_prices BCH/BNB ===")
d = json.load(open("/root/MINA_v2/initial_prices.json"))
for k,v in d.items():
    if "BCH" in k or "BNB" in k:
        print(k, v)
conn.close()
'''
sftp = c.open_sftp()
with sftp.file('/tmp/_derr_q.py', 'w') as f:
    f.write(script)
sftp.close()

cmds = [
    ('DERR queries', '/root/MINA_v2/venv/bin/python /tmp/_derr_q.py'),
    ('D1 gerceklestirildi bugun', "journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager | grep -E 'BCHUSDT|BNBUSDT' | grep -iE 'gerçekleştirildi|ağırlıklı|Journal.*D'"),
]
for title, cmd in cmds:
    print('='*90)
    print(title)
    print('='*90)
    _, out, err = c.exec_command(cmd, timeout=120)
    print(out.read().decode('utf-8', errors='replace') or '(bos)')
    e = err.read().decode('utf-8', errors='replace')
    if e.strip(): print('stderr:', e)
    print()
c.close()
