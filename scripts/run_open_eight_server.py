#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
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
