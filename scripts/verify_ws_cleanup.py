#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko, os
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(),timeout=30)
for cmd in [
    "test -f /root/MINA_v2/dashboard_ws.py && echo EXISTS || echo DELETED",
    "systemctl cat mina-dashboard-ws.service | grep ExecStart",
    "ps aux | grep dashboard_ws | grep -v grep",
]:
    print(">>>", cmd)
    _,o,_=c.exec_command(cmd,timeout=15)
    print(o.read().decode())
c.close()
