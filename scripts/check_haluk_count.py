#!/usr/bin/env python3
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
cmd = "/root/MINA_v2/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); print(c.execute('SELECT COUNT(*) FROM haluk_messages').fetchone()[0])\""
_, o, e = c.exec_command(cmd, timeout=20)
print(o.read().decode())
print(e.read().decode())
c.close()
