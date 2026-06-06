#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Listener + signal_parser deploy ve kısa test."""
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "signal_bot/listener.py",
    "signal_bot/signal_parser.py",
    "signal_bot/haluk_pdf_parser.py",
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = c.open_sftp()

    for rel in FILES:
        local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print(f">>> PUT {rel}")
        sftp.put(local, remote)

    restart_cmd = (
        f"systemctl stop mina-listener.service 2>/dev/null || true; "
        f"if [ -f {REMOTE}/signal_bot/listener.lock ]; then "
        f"kill -9 $(cat {REMOTE}/signal_bot/listener.lock) 2>/dev/null || true; fi; "
        f"pkill -9 -f '{REMOTE}/venv/bin/python signal_bot/listener.py' 2>/dev/null || true; "
        f"sleep 2; rm -f {REMOTE}/signal_bot/listener.lock; "
        f"systemctl reset-failed mina-listener.service 2>/dev/null || true; "
        f"systemctl start mina-listener.service; sleep 5; "
        f"systemctl is-active mina-listener.service; "
        f"tail -4 {REMOTE}/signal_bot/signals_log.txt"
    )
    print(">>> RESTART mina-listener.service")
    _, out, err = c.exec_command(restart_cmd, timeout=60)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()
    print("DONE")


if __name__ == "__main__":
    main()
