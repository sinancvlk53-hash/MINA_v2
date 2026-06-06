#!/usr/bin/env python3
import os
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
LOCAL = os.path.join(os.path.dirname(__file__), "verify_macro_ws.py")
REMOTE = "/root/MINA_v2/scripts/verify_macro_ws.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
_, o, e = c.exec_command(
    f"cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python scripts/verify_macro_ws.py",
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
print(e.read().decode("utf-8", errors="replace"))
c.close()
