#!/usr/bin/env python3
import os, sys, time, paramiko
sys.stdout.reconfigure(encoding="utf-8")
LOCAL = os.path.join(os.path.dirname(__file__), "query_derr_remote.py")
REMOTE = "/root/MINA_v2/scripts/query_derr_remote.py"
c = None
for i in range(8):
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect("178.105.150.40", "root", password=os.environ.get("MINA_SSH_PASS", "REDACTED"), timeout=25)
        break
    except Exception as ex:
        if i == 7:
            raise SystemExit(f"SSH failed: {ex}")
        time.sleep(4)
sftp = c.open_sftp()
try:
    sftp.mkdir("/root/MINA_v2/scripts")
except OSError:
    pass
sftp.put(LOCAL, REMOTE)
_, o, e = c.exec_command(f"/root/MINA_v2/venv/bin/python {REMOTE}", timeout=30)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
c.close()
