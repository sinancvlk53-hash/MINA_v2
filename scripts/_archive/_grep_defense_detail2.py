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

queries = [
    ("D1/D2 execution stdout bugun", r"journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager | grep -E 'BCHUSDT|BNBUSDT' | grep -iE 'D1 gerçekleştirildi|D2 gerçekleştirildi|Journal.*D[123]|ağırlıklı|ekleme hatası|defense'"),
    ("DERR schema trades", r"sqlite3 /root/MINA_v2/mina_trading_journal.db \"PRAGMA table_info(trades);\""),
    ("DERR BCH BNB open", r"sqlite3 -header -column /root/MINA_v2/mina_trading_journal.db \"SELECT id,symbol,side,leverage,defense_triggered,defense_prices,status,created_at,close_time,pnl_usdt FROM trades WHERE symbol IN ('BCHUSDT','BNBUSDT') ORDER BY id DESC LIMIT 5;\""),
    ("DERR XRP AVAX closed today", r"sqlite3 -header -column /root/MINA_v2/mina_trading_journal.db \"SELECT id,symbol,side,leverage,status,close_reason,pnl_usdt,created_at,close_time FROM trades WHERE symbol IN ('XRPUSDT','AVAXUSDT') AND date(created_at)='2026-06-03' ORDER BY close_time DESC;\""),
    ("initial_prices", r"python3 -c \"import json;d=json.load(open('/root/MINA_v2/initial_prices.json'));print(json.dumps({k:v for k,v in d.items() if 'BCH' in k or 'BNB' in k},indent=2))\""),
]

for title, cmd in queries:
    print('='*90)
    print(title)
    print('='*90)
    _, out, err = c.exec_command(cmd, timeout=120)
    data = out.read().decode('utf-8', errors='replace')
    print(data.strip() if data.strip() else '(bos)')
    e = err.read().decode('utf-8', errors='replace')
    if e.strip(): print('stderr:', e)
    print()

c.close()
