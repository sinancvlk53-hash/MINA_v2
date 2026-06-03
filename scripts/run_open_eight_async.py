#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sunucuda açılışı log dosyasına yazar, sonra tail."""
import os
import sys
import time
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOG = f"{REMOTE}/open_eight_last.log"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()
    for rel in ("open_fast_coins.py", "open_eight_positions.py"):
        sftp.put(os.path.join(LOCAL, rel), f"{REMOTE}/{rel}")

    cmd = (
        f"cd {REMOTE} && "
        f"nohup {REMOTE}/venv/bin/python open_eight_positions.py > {LOG} 2>&1 & "
        f"echo STARTED_PID=$!"
    )
    _, o, _ = c.exec_command(cmd, timeout=15)
    print(o.read().decode())

    for i in range(90):
        time.sleep(5)
        _, o, _ = c.exec_command(f"tail -30 {LOG} 2>/dev/null; grep -c FINAL_ {LOG} 2>/dev/null", timeout=20)
        chunk = o.read().decode("utf-8", errors="replace")
        if "FINAL_OPEN_POSITION_COUNT" in chunk:
            _, o2, _ = c.exec_command(f"cat {LOG}", timeout=30)
            print(o2.read().decode("utf-8", errors="replace"))
            break
        if i % 6 == 0:
            print(f"... bekleniyor ({(i+1)*5}s)")
    else:
        _, o2, _ = c.exec_command(f"cat {LOG}", timeout=60)
        print(o2.read().decode("utf-8", errors="replace"))

    c.close()


if __name__ == "__main__":
    main()
