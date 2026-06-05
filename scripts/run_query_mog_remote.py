#!/usr/bin/env python3
import os
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
LOCAL = os.path.join(os.path.dirname(__file__), "query_mog_orders.py")
REMOTE = "/root/MINA_v2/scripts/query_mog_orders.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
sftp.close()
print("Running on server...\n")
_, o, e = c.exec_command(f"/root/MINA_v2/venv/bin/python {REMOTE}", timeout=120)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
c.close()
