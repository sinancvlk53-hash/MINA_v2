#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Journal fix + engine.lock — deploy ve restart."""
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["mina_position_manager.py", "main.py"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = c.open_sftp()

    for rel in FILES:
        local = os.path.join(LOCAL_ROOT, rel)
        remote = f"{REMOTE}/{rel}"
        print(f">>> PUT {rel}")
        sftp.put(local, remote)

    cmds = [
        "systemctl restart mina-engine.service",
        "sleep 3",
        "systemctl is-active mina-engine.service",
        "pgrep -af 'python.*main.py' | head -1",
    ]
    for cmd in cmds:
        print(f">>> {cmd}")
        _, out, err = c.exec_command(cmd, timeout=30)
        o = out.read().decode().strip()
        if o:
            print(o)
        e = err.read().decode().strip()
        if e:
            print("ERR:", e)

    c.close()
    print(">>> Deploy tamam — doğrulama için: python scripts/post_deploy_verify.py")


if __name__ == "__main__":
    main()
