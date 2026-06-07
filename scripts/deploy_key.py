#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SSH key ile deploy — MINA_SSH_PASS gerektirmez."""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.environ.get("MINA_SSH_HOST", "178.105.150.40")
USER = os.environ.get("MINA_SSH_USER", "root")
REMOTE = "/root/MINA_v2"

FILES = [
    "mina_ssh.py",
    "mina_rate_limit.py",
    "mina_exchange_info.py",
    "mina_binance_retry.py",
    "mina_manual_override.py",
    "mina_manual_slot.py",
    "mina_motor_telegram.py",
    "mina_system_alerts.py",
    "mina_daily_summary.py",
    "mina_copy_trading.py",
    "mina_position_manager.py",
    "mina_trading_journal.py",
    "mina_dashboard_settings.py",
    "main.py",
    "requirements.txt",
    "backend/config.py",
    "dashboard/dashboard_ws.py",
    "scripts/manual_open.py",
    "signal_bot/merter_dca_manager.py",
    "signal_bot/signal_parser.py",
    "signal_bot/haluk_predictions.py",
    "mina_coin_lock.py",
    "scripts/system_health_audit.py",
    ".env.example",
]


def run(cmd: list[str] | str, check: bool = False) -> subprocess.CompletedProcess:
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd))
    if isinstance(cmd, str):
        return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def main() -> None:
    os.chdir(ROOT)
    for rel in FILES:
        lp = os.path.join(ROOT, rel.replace("/", os.sep))
        rp = f"{REMOTE}/{rel}"
        r = run(["scp", "-q", lp, f"{USER}@{HOST}:{rp}"])
        if r.returncode != 0:
            print(r.stderr)
            sys.exit(r.returncode)
        print(f"PUT {rel}")

    dist_local = os.path.join(ROOT, "dashboard", "dist")
    if os.path.isdir(dist_local):
        r = run(["scp", "-rq", dist_local, f"{USER}@{HOST}:{REMOTE}/dashboard/"])
        if r.returncode != 0:
            print(r.stderr)
            sys.exit(r.returncode)
        print("PUT dashboard/dist/")

    remote_cmds = [
        f"cd {REMOTE} && venv/bin/pip install -q aiohttp 2>/dev/null || true",
        "systemctl restart mina-engine.service",
        "systemctl restart mina-listener.service",
        "systemctl restart mina-merter-dca.service",
        "systemctl restart mina-dashboard-ws.service",
        "systemctl restart mina-dashboard-vite.service",
        "sleep 4",
        f"{REMOTE}/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('{REMOTE}/mina_trading_journal.db',timeout=30); print('journal_mode', c.execute('PRAGMA journal_mode').fetchone()[0])\"",
        "systemctl is-active mina-engine mina-merter-dca mina-dashboard-ws mina-dashboard-vite mina-listener",
        f"test -f {REMOTE}/position_states.json && echo position_states.json OK || echo position_states.json MISSING",
        f"test -f {REMOTE}/mina_position_state.json && echo mina_position_state.json OK || echo mina_position_state.json MISSING",
        f"{REMOTE}/venv/bin/python {REMOTE}/scripts/system_health_audit.py",
        'curl -s -o /dev/null -w "dashboard HTTP %{http_code}\\n" http://127.0.0.1:3000/',
    ]
    for cmd in remote_cmds:
        r = run(["ssh", f"{USER}@{HOST}", cmd])
        if r.stdout:
            print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr)

    print("DEPLOY KEY DONE")


if __name__ == "__main__":
    main()
