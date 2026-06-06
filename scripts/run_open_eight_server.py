#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os
import sys
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()
    for rel in ("open_fast_coins.py", "open_eight_positions.py"):
        sftp.put(os.path.join(LOCAL, rel), f"{REMOTE}/{rel}")
    cmd = f"cd {REMOTE} && {REMOTE}/venv/bin/python open_eight_positions.py 2>&1"
    _, out, err = c.exec_command(cmd, timeout=600)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()


if __name__ == "__main__":
    main()
