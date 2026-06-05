#!/usr/bin/env python3
import os
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
for rel in ("signal_bot/signal_parser.py", "scripts/refresh_macro_from_pdf.py"):
    sftp.put(os.path.join(LOCAL, rel.replace("/", os.sep)), f"/root/MINA_v2/{rel}")
    print("PUT", rel)
sftp.close()
cmds = [
    "/root/MINA_v2/venv/bin/python /root/MINA_v2/scripts/refresh_macro_from_pdf.py",
    "systemctl restart mina-listener.service",
    "sleep 2 && systemctl is-active mina-listener.service",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
