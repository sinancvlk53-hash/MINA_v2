#!/usr/bin/env python3
import os, sys, time
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
time.sleep(35)
cmds = [
    "grep -E 'SOLUSDT|D2|execute FAILED|icra' /root/MINA_v2/mina_bot.log | tail -15",
    "journalctl -u mina-engine.service --since '2 min ago' --no-pager | grep -iE 'SOL|D2|D3|execute|icra|kaçış|ekleme' | tail -20",
    "cat /root/MINA_v2/defense_levels.json",
    "cat /root/MINA_v2/mina_position_state.json | python3 -c \"import sys,json; print(json.dumps(json.load(sys.stdin).get('SOLUSDT',{}), indent=2))\"",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    print(f"$ {cmd}\n{o.read().decode()}{e.read().decode()}\n")
c.close()
