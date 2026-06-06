#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Pipeline + queue_watcher deploy ve sunucuda baseline + arka plan izleyici."""
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "signal_bot/signal_pipeline.py",
    "signal_bot/signal_guillotine.py",
    "signal_bot/queue_watcher.py",
    "signal_bot/listener.py",
    "mina_trading_journal.py",
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()
    for rel in FILES:
        sftp.put(os.path.join(LOCAL, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
        print(f">>> {rel}")

    sftp.put(
        os.path.join(LOCAL, "systemd", "mina-queue-watcher.service"),
        "/etc/systemd/system/mina-queue-watcher.service",
    )
    print(">>> systemd mina-queue-watcher.service")

    cmd = (
        f"cd {REMOTE} && {REMOTE}/venv/bin/python signal_bot/queue_watcher.py --baseline && "
        f"systemctl daemon-reload && "
        f"systemctl enable mina-queue-watcher.service && "
        f"systemctl restart mina-queue-watcher.service && "
        f"systemctl restart mina-listener.service 2>/dev/null; "
        f"sleep 2 && "
        f"systemctl is-active mina-queue-watcher mina-listener && "
        f"pgrep -af queue_watcher | head -2"
    )
    print(">>> sunucu baseline + watcher + listener restart")
    _, out, err = c.exec_command(cmd, timeout=30)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("stderr:", e)
    c.close()
    print("DONE — gerçek Merter sinyali bekleniyor.")


if __name__ == "__main__":
    main()
