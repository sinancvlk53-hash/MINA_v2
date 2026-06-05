#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "scripts/reset_and_open_six.py",
    "open_fast_coins.py",
    "mina_position_manager.py",
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    for rel in FILES:
        sftp.put(os.path.join(LOCAL, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
        print(f">>> PUT {rel}")
    sftp.close()

    cmd = (
        f"cd {REMOTE} && "
        f"/root/MINA_v2/venv/bin/python -u scripts/reset_and_open_six.py 2>&1; "
        f"echo '---'; "
        f"systemctl restart mina-engine.service && sleep 2 && "
        f"systemctl is-active mina-engine.service"
    )
    print(">>> RUN reset_and_open_six.py")
    _, out, err = c.exec_command(cmd, timeout=300)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("stderr:", e)
    c.close()


if __name__ == "__main__":
    main()
