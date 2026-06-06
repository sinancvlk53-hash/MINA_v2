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
LOCAL = os.path.join(os.path.dirname(__file__), "clean_labusdt_ghost.py")
REMOTE = "/root/MINA_v2/scripts/clean_labusdt_ghost.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
sftp.close()
print("Running LABUSDT cleanup on server...\n")
_, o, e = c.exec_command(f"/root/MINA_v2/venv/bin/python {REMOTE}", timeout=120)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
c.close()
