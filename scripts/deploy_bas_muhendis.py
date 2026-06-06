#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Baş Mühendis paketi deploy."""
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "mina_slot_policy.py",
    "main.py",
    "mina_position_manager.py",
    "MINA_ANAYASASI.md",
    "backend/ghost_positions.py",
    "signal_bot/merter_dca_manager.py",
    "signal_bot/signal_slot_bridge.py",
    "scripts/manual_open.py",
    "scripts/clean_labusdt_ghost.py",
    "dashboard/dashboard_ws.py",
]


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    for rel in FILES:
        lp = os.path.join(LOCAL, rel.replace("/", os.sep))
        rp = f"{REMOTE}/{rel}"
        print("PUT", rel)
        sftp.put(lp, rp)
    sftp.close()

    cmds = [
        f"{REMOTE}/venv/bin/python {REMOTE}/scripts/clean_labusdt_ghost.py",
        "systemctl restart mina-engine.service",
        "systemctl restart mina-merter-dca.service",
        "systemctl restart mina-dashboard-ws.service",
        "sleep 3",
        "systemctl is-active mina-engine.service mina-merter-dca.service mina-dashboard-ws.service",
    ]
    for cmd in cmds:
        print(">>>", cmd)
        _, o, e = c.exec_command(cmd, timeout=90)
        print(o.read().decode("utf-8", errors="replace"))
        er = e.read().decode("utf-8", errors="replace")
        if er.strip():
            print("ERR:", er)
    c.close()
    print("DONE")


if __name__ == "__main__":
    main()
