#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Merter DCA modülü deploy + servis restart."""
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "signal_bot/merter_dca_manager.py",
    "signal_bot/merter_dca_runner.py",
    "signal_bot/signal_parser.py",
    "signal_bot/listener.py",
    "mina_trading_journal.py",
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

    sftp.put(
        os.path.join(LOCAL, "systemd", "mina-merter-dca.service"),
        "/etc/systemd/system/mina-merter-dca.service",
    )
    sftp.put(
        os.path.join(LOCAL, "signal_bot", "test_merter_dca.py"),
        f"{REMOTE}/signal_bot/test_merter_dca.py",
    )
    print(">>> PUT systemd/mina-merter-dca.service")

    cmd = (
        f"cd {REMOTE} && "
        f"systemctl stop mina-listener.service 2>/dev/null; "
        f"pkill -9 -f signal_bot/listener.py 2>/dev/null; "
        f"rm -f signal_bot/listener.lock; "
        f"systemctl daemon-reload && "
        f"systemctl enable mina-merter-dca.service && "
        f"systemctl restart mina-merter-dca.service && "
        f"systemctl restart mina-listener.service && "
        f"systemctl restart mina-queue-watcher.service && "
        f"sleep 3 && "
        f"systemctl is-active mina-listener.service mina-queue-watcher.service mina-merter-dca.service && "
        f"{REMOTE}/venv/bin/python signal_bot/test_merter_dca.py 2>&1 | head -55"
    )
    print(">>> restart + test")
    _, out, err = c.exec_command(cmd, timeout=120)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("stderr:", e)
    c.close()
    print(">>> Deploy tamamlandı.")


if __name__ == "__main__":
    main()
