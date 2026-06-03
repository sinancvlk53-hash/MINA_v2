#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""signal_slot_bridge + mina_position_manager deploy ve engine restart."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "mina_position_manager.py",
    "signal_bot/signal_slot_bridge.py",
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

    cmds = [
        f"test -f {REMOTE}/signal_bot/signal_slot_bridge.py && echo 'bridge_ok'",
        f"grep -c try_fill_freed_slot {REMOTE}/mina_position_manager.py",
        "systemctl restart mina-engine.service",
        "sleep 3",
        "systemctl is-active mina-engine.service",
        "systemctl status mina-engine.service --no-pager -l | head -15",
        "pgrep -af 'python.*main.py' | head -1",
    ]
    for cmd in cmds:
        print(f">>> {cmd}")
        _, out, err = c.exec_command(cmd, timeout=45)
        o = out.read().decode().strip()
        if o:
            print(o)
        e = err.read().decode().strip()
        if e:
            print("ERR:", e)

    sftp.close()
    c.close()
    print(">>> Deploy tamamlandı.")


if __name__ == "__main__":
    main()
