#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""signal_parser.py (+ filtre) deploy + listener/watcher restart."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "signal_bot/signal_parser.py",
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()

    for rel in FILES:
        local = os.path.join(LOCAL, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print(f">>> PUT {rel}")
        sftp.put(local, remote)

    cmds = [
        f"grep -c '_select_filtered_bot_record' {REMOTE}/signal_bot/signal_parser.py",
        f"grep -c 'merter_filter.log' {REMOTE}/signal_bot/signal_parser.py",
        "systemctl restart mina-listener.service",
        "systemctl restart mina-queue-watcher.service",
        "sleep 2",
        "systemctl is-active mina-listener.service",
        "systemctl is-active mina-queue-watcher.service",
        "systemctl status mina-listener.service --no-pager -l | head -12",
        "systemctl status mina-queue-watcher.service --no-pager -l | head -12",
        "pgrep -af 'signal_bot/listener.py' | head -1",
        "pgrep -af 'signal_bot/queue_watcher.py' | head -1",
        f"test -f {REMOTE}/signal_bot/merter_filter.log && tail -3 {REMOTE}/signal_bot/merter_filter.log || echo 'merter_filter.log: henuz yok'",
    ]
    for cmd in cmds:
        print(f">>> {cmd}")
        _, out, err = c.exec_command(cmd, timeout=45)
        o = out.read().decode("utf-8", errors="replace").strip()
        if o:
            print(o)
        e = err.read().decode("utf-8", errors="replace").strip()
        if e:
            print("ERR:", e)

    sftp.close()
    c.close()
    print(">>> Deploy tamamlandı.")


if __name__ == "__main__":
    main()
