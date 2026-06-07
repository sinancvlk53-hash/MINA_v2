#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
_, o, _ = c.exec_command(
    "journalctl -u mina-engine.service -n 30 --no-pager 2>&1; "
    "echo '---'; "
    "ls -la /root/MINA_v2/engine.lock; "
    "cat /root/MINA_v2/engine.lock 2>/dev/null",
    timeout=60,
)
text = o.read().decode('utf-8', errors='replace')
path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine_journal_out.txt")
open(path, "w", encoding="utf-8").write(text)
print(path)
c.close()
