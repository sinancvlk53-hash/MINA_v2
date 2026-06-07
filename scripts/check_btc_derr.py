#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
cmd = (
    "/root/MINA_v2/venv/bin/python -c \""
    "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); c.row_factory=sqlite3.Row; "
    "rows=c.execute('SELECT id,symbol,status,close_reason,close_time,pnl_usdt,close_price FROM trades WHERE symbol IN (\\\"BTCUSDT\\\",\\\"SOLUSDT\\\") ORDER BY id DESC LIMIT 4').fetchall(); "
    "[print(dict(r)) for r in rows]\""
)
_, o, _ = c.exec_command(cmd, timeout=30)
print(o.read().decode())
c.close()
