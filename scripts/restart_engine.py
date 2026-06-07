#!/usr/bin/env python3
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
cmds = [
    "systemctl restart mina-engine.service",
    "sleep 35",
    "systemctl show mina-engine -p MainPID --value",
    "grep -E 'FAILED|icra tamamlanmadi|D2 ekleme|D2 y' /root/MINA_v2/mina_bot.log | tail -10",
    "cat /root/MINA_v2/mina_position_state.json | python3 -c \"import sys,json; print(json.dumps(json.load(sys.stdin).get('SOLUSDT',{}), indent=2))\"",
]
out = []
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=90)
    out.append(f"$ {cmd}\n{o.read().decode('utf-8', errors='replace')}")
path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine_restart_out.txt")
open(path, "w", encoding="utf-8").write("\n".join(out))
print(path)
c.close()
