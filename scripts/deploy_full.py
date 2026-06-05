#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tam deploy — tüm güncel dosyalar + servis restart."""
from __future__ import annotations

import io
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "main.py",
    "mina_dashboard_settings.py",
    "mina_position_manager.py",
    "mina_slot_policy.py",
    "mina_tracking.py",
    "mina_signal_source.py",
    "mina_entry_orders.py",
    "mina_trading_journal.py",
    "scripts/reconcile_atom_derr.py",
    "backend/ghost_positions.py",
    "signal_bot/listener.py",
    "signal_bot/signal_parser.py",
    "signal_bot/haluk_pdf_parser.py",
    "signal_bot/macro_levels_store.py",
    "signal_bot/signal_slot_bridge.py",
    "signal_bot/merter_dca_manager.py",
    "signal_bot/merter_dca_runner.py",
    "signal_bot/approval_bot.py",
    "scripts/manual_open.py",
    "tools/telegram_bot.py",
    "dashboard/dashboard_ws.py",
]

SERVICES = [
    "mina-engine.service",
    "mina-listener.service",
    "mina-merter-dca.service",
    "mina-queue-watcher.service",
    "mina-dashboard-ws.service",
    "mina-dashboard-vite.service",
]


def ensure_remote_dir(sftp, path: str) -> None:
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting {HOST}...")
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()

    for rel in FILES:
        lp = os.path.join(LOCAL, rel.replace("/", os.sep))
        rp = f"{REMOTE}/{rel}"
        if not os.path.isfile(lp):
            print(f"SKIP (missing): {rel}")
            continue
        print(f"PUT {rel}")
        sftp.put(lp, rp)

    dist_local = os.path.join(LOCAL, "dashboard", "dist")
    dist_remote = f"{REMOTE}/dashboard/dist"
    ensure_remote_dir(sftp, dist_remote)
    for root, _, files in os.walk(dist_local):
        rel = os.path.relpath(root, dist_local).replace("\\", "/")
        remote_dir = dist_remote if rel == "." else f"{dist_remote}/{rel}"
        ensure_remote_dir(sftp, remote_dir)
        for f in files:
            lp = os.path.join(root, f)
            rp = f"{remote_dir}/{f}"
            print(f"PUT dashboard/dist/{rel}/{f}" if rel != "." else f"PUT dashboard/dist/{f}")
            sftp.put(lp, rp)

    sftp.close()

    listener_clean = (
        f"systemctl stop mina-listener.service 2>/dev/null || true; "
        f"if [ -f {REMOTE}/signal_bot/listener.lock ]; then "
        f"kill -9 $(cat {REMOTE}/signal_bot/listener.lock) 2>/dev/null || true; fi; "
        f"pkill -9 -f '{REMOTE}/venv/bin/python signal_bot/listener.py' 2>/dev/null || true; "
        f"sleep 2; rm -f {REMOTE}/signal_bot/listener.lock; "
        f"systemctl reset-failed mina-listener.service 2>/dev/null || true; "
    )

    restart_cmds = [
        listener_clean + "systemctl restart mina-engine.service",
        "systemctl restart mina-merter-dca.service",
        "systemctl restart mina-queue-watcher.service 2>/dev/null || true",
        "systemctl start mina-listener.service",
        "systemctl restart mina-dashboard-ws.service",
        "systemctl restart mina-dashboard-vite.service",
        "sleep 4",
        "systemctl is-active " + " ".join(SERVICES),
        f"tail -3 {REMOTE}/signal_bot/signals_log.txt 2>/dev/null || true",
        'curl -s -o /dev/null -w "dashboard HTTP %{http_code}\\n" http://127.0.0.1:3000/',
    ]

    for cmd in restart_cmds:
        print(">>>", cmd[:120] + ("..." if len(cmd) > 120 else ""))
        _, o, e = c.exec_command(cmd, timeout=120)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print("ERR:", err)

    c.close()
    print("DEPLOY DONE")


if __name__ == "__main__":
    main()
