#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
cmds = [
    "/root/MINA_v2/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); c.row_factory=sqlite3.Row; rows=c.execute('SELECT id,symbol,status,defense_triggered,close_reason,close_time FROM trades WHERE symbol=\\\"LINKUSDT\\\" ORDER BY id DESC LIMIT 3').fetchall(); [print(dict(r)) for r in rows]\"",
    "journalctl -u mina-engine.service --since '2026-06-07 10:20:00' --until '2026-06-07 10:35:00' --no-pager 2>/dev/null | grep -iE 'LINK|D3|SFP|defense' || echo '(journal bos)'",
    "grep -i 'SFP\\|D3\\|LINKUSDT' /root/MINA_v2/mina_bot.log | tail -5",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    print(f"$ {cmd}\n{o.read().decode()}{e.read().decode()}\n")
c.close()
