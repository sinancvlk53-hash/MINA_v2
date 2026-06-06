#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "/root/MINA_v2"

files = [
    "backend/ghost_positions.py",
    "scripts/clean_tracking_symbols.py",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
for rel in files:
    sftp.put(os.path.join(LOCAL_ROOT, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
    print("PUT", rel)
sftp.close()

cmds = [
    f"{REMOTE}/venv/bin/python {REMOTE}/scripts/clean_tracking_symbols.py",
    "systemctl restart mina-engine.service",
    "sleep 2",
    "systemctl is-active mina-engine.service",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
print("DONE")
