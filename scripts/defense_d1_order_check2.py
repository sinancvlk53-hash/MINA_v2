#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)
cmds = [
    "grep -E 'LINKUSDT|D1|defense|Journal|futures_create|MARKET|ekleme|margin' /root/MINA_v2/mina_bot.log | tail -40",
    "cat /root/MINA_v2/initial_margins.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps({k:v for k,v in d.items() if 'LINK' in k}, indent=2))\"",
    "/root/MINA_v2/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); print(c.execute('SELECT name FROM sqlite_master WHERE type=\\\"table\\\"').fetchall())\"",
    "/root/MINA_v2/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); c.row_factory=sqlite3.Row; rows=c.execute('SELECT * FROM trades WHERE id=30').fetchone(); print(dict(rows) if rows else 'none')\"",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    print(f"$ {cmd}\n{o.read().decode()}{e.read().decode()}\n")
c.close()
