# -*- coding: utf-8 -*-
"""Sunucuya dosya kopyala + bootstrap + systemd ExecStart güncelle."""

from __future__ import annotations

import io
import os
import sys

import paramiko

HOST = "178.105.150.40"
USER = "root"
PASS = "REDACTED"
REMOTE = "/root/MINA_v2"

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "main.py",
    "mina_position_manager.py",
    "mina_trading_journal.py",
    "mina_tracking.py",
    "backend/config.py",
    "backend/position_manager.py",
    "backend/main.py",
    "scripts/bootstrap_production.py",
]


def main() -> None:
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

    vpy = f"{REMOTE}/venv/bin/python"
    cmd = (
        f"cd {REMOTE} && "
        f"{REMOTE}/venv/bin/pip install -q -r requirements.txt; "
        f"MINA_DATA_ROOT={REMOTE} {vpy} scripts/bootstrap_production.py"
    )
    print(f">>> RUN {cmd}")
    _, out, err = c.exec_command(cmd, timeout=120)
    print("--- STDOUT ---")
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("--- STDERR ---")
        print(e)

    svc = f"""[Unit]
Description=MINA v2 Trading Engine (MinaPositionManager)
After=network.target

[Service]
Type=simple
WorkingDirectory={REMOTE}
Environment=MINA_DATA_ROOT={REMOTE}
ExecStart={REMOTE}/venv/bin/python {REMOTE}/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    print(">>> WRITE /etc/systemd/system/mina-engine.service")
    sftp.putfo(io.BytesIO(svc.encode()), "/etc/systemd/system/mina-engine.service")
    for cmd2 in (
        "systemctl daemon-reload",
        "systemctl restart mina-engine.service",
        "systemctl is-active mina-engine.service",
    ):
        print(f">>> {cmd2}")
        _, o, _ = c.exec_command(cmd2)
        print(o.read().decode().strip())

    print(">>> REMOTE initial_entry_prices.json")
    _, o, _ = c.exec_command(f"cat {REMOTE}/initial_entry_prices.json")
    print(o.read().decode())

    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
