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
cmd = "journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager | grep -E 'XRPUSDT|AVAXUSDT' | grep -iE 'TP|trailing|take_profit|kapat|profit|max_prices|entry|SHORT'"
_, out, err = c.exec_command(cmd, timeout=120)
data = out.read().decode('utf-8', errors='replace')
print(data if data.strip() else '(bos)')
print('--- lines:', len(data.splitlines()))
c.close()
