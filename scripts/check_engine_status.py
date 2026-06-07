#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
out = []
cmds = [
    "systemctl is-active mina-engine.service",
    "grep -c _incomplete_defense_level /root/MINA_v2/mina_position_manager.py",
    "tail -8 /root/MINA_v2/mina_bot.log",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    out.append(f"$ {cmd}\n{o.read().decode('utf-8', errors='replace')}")
c.close()
path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine_check_out.txt")
open(path, "w", encoding="utf-8").write("\n".join(out))
print(path)
