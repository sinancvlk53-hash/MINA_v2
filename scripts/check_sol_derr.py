#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
_, o, _ = c.exec_command(
    "/root/MINA_v2/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); c.row_factory=sqlite3.Row; r=c.execute('SELECT defense_triggered,defense_prices,weighted_avg_price FROM trades WHERE id=29').fetchone(); print(dict(r))\"",
    timeout=30,
)
print(o.read().decode())
c.close()
