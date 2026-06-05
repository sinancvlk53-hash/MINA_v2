#!/usr/bin/env python3
import os, sys, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40', username='root', password=os.environ.get('MINA_SSH_PASS','REDACTED'), timeout=25)
cmd = "journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager | grep -E 'XRPUSDT|AVAXUSDT' | grep -iE 'TP|trailing|take_profit|kapat|profit|max_prices|entry|SHORT'"
_, out, err = c.exec_command(cmd, timeout=120)
data = out.read().decode('utf-8', errors='replace')
print(data if data.strip() else '(bos)')
print('--- lines:', len(data.splitlines()))
c.close()
