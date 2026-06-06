#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, sys, sqlite3, json, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=25)

cmds = [
    ("DERR trades BCH/BNB", """/root/MINA_v2/venv/bin/python - <<'PY'
import sqlite3, json
c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db')
c.row_factory=sqlite3.Row
cur=c.cursor()
cur.execute("SELECT id,symbol,side,entry_price,leverage,defense_triggered,defense_prices,weighted_avg,status,created_at,close_time FROM trades WHERE symbol IN ('BCHUSDT','BNBUSDT') ORDER BY created_at DESC LIMIT 10")
for r in cur.fetchall():
    print(dict(r))
c.close()
PY"""),
    ("JOURNAL D1 stdout bugun", "journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager 2>/dev/null | grep -E 'BCHUSDT|BNBUSDT' | grep -iE 'D1|D2|gerçekleştirildi|ağırlıklı|ekleme|initial_entry|entry' || true"),
    ("initial_prices BCH/BNB", "python3 -c \"import json; d=json.load(open('/root/MINA_v2/initial_prices.json')); print({k:v for k,v in d.items() if 'BCH' in k or 'BNB' in k})\""),
    ("defense_levels BCH/BNB", "python3 -c \"import json; d=json.load(open('/root/MINA_v2/defense_levels.json')); print({k:v for k,v in d.items() if 'BCH' in k or 'BNB' in k})\""),
    ("DERR XRP/AVAX trades", """/root/MINA_v2/venv/bin/python - <<'PY'
import sqlite3
c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db')
c.row_factory=sqlite3.Row
cur=c.cursor()
cur.execute("SELECT id,symbol,side,entry_price,leverage,status,close_reason,pnl_usdt,created_at,close_time FROM trades WHERE symbol IN ('XRPUSDT','AVAXUSDT') AND date(created_at)='2026-06-03' ORDER BY close_time DESC")
for r in cur.fetchall():
    print(dict(r))
c.close()
PY"""),
]

for title, cmd in cmds:
    print('='*90)
    print(title)
    print('='*90)
    _, out, err = c.exec_command(cmd, timeout=90)
    print(out.read().decode('utf-8', errors='replace') or '(bos)')
    e = err.read().decode('utf-8', errors='replace')
    if e.strip(): print('stderr:', e)
    print()

c.close()
