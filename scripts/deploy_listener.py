#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Listener + signal_parser deploy ve kısa test."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
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

    test_cmd = (
        f"cd {REMOTE} && "
        f"systemctl stop mina-listener.service mina-ht-listener.service 2>/dev/null; "
        f"pkill -9 -f signal_bot/listener.py 2>/dev/null; "
        f"pkill -9 -f signal_bot/ht_listener.py 2>/dev/null; "
        f"sleep 1; rm -f signal_bot/listener.lock; "
        f"{REMOTE}/venv/bin/pip install -q pdfplumber 2>/dev/null; "
        f"timeout 45 {REMOTE}/venv/bin/python -u signal_bot/listener.py 2>&1 || true"
    )
    print(">>> TEST (45s dinleme, ilk mesaj terminalde)")
    _, out, err = c.exec_command(test_cmd, timeout=60)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()
    print("DONE")


if __name__ == "__main__":
    main()
