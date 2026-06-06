#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
import os

PASS = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", username="root", password=PASS, timeout=30)
s = c.open_sftp()
s.put("ops/backup_mina.sh", "/root/MINA_v2/ops/backup_mina.sh")
s.close()
for cmd in [
    "sed -i 's/\\r$//' /root/MINA_v2/ops/backup_mina.sh",
    "chmod +x /root/MINA_v2/ops/backup_mina.sh",
    "bash /root/MINA_v2/ops/backup_mina.sh",
    "ls -lt /root/backups/*.tar.gz | head -2",
    "crontab -l | grep backup_mina",
]:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
