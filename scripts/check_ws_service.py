#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko, os
PASS = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", username="root", password=PASS, timeout=30)
cmds = [
    "systemctl cat mina-dashboard-ws.service",
    "ps aux | grep -E 'dashboard_ws|8765' | grep -v grep",
    "grep -n macroLevels /root/MINA_v2/dashboard/dashboard_ws.py | head -5",
    "grep -n macroLevels /root/MINA_v2/dashboard_ws.py 2>/dev/null | head -5",
    "head -5 /root/MINA_v2/dashboard/dashboard_ws.py",
    "wc -l /root/MINA_v2/dashboard/dashboard_ws.py /root/MINA_v2/dashboard_ws.py 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=15)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
