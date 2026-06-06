#!/usr/bin/env python3
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
cmds = [
    "cat /root/MINA_v2/dashboard/dist/index.html",
    "systemctl cat mina-dashboard-vite.service 2>/dev/null | head -30",
    "ls -la /root/MINA_v2/dashboard/dist/assets/*.js 2>/dev/null | tail -5",
    "grep -o 'macroLevels' /root/MINA_v2/dashboard/dist/assets/*.js 2>/dev/null | head -3",
    "grep -l 'Haluk Makro' /root/MINA_v2/dashboard/dist/assets/*.js 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=15)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
