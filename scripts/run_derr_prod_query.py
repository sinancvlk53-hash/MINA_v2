#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, sys, time, paramiko
sys.stdout.reconfigure(encoding="utf-8")
LOCAL = os.path.join(os.path.dirname(__file__), "query_derr_prod.py")
for i in range(10):
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=25)
        sftp = c.open_sftp()
        sftp.put(LOCAL, "/tmp/query_derr_prod.py")
        _, o, e = c.exec_command("/root/MINA_v2/venv/bin/python /tmp/query_derr_prod.py", timeout=45)
        print(o.read().decode("utf-8", errors="replace"))
        err = e.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR:", err)
        c.close()
        sys.exit(0)
    except Exception as ex:
        print(f"attempt {i+1}: {ex}")
        time.sleep(2)
sys.exit(1)
