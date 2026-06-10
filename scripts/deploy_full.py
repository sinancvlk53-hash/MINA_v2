#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tam deploy — tüm güncel dosyalar + servis restart."""
from __future__ import annotations

import io
import os
import subprocess
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

import paramiko

HOST, USER = SSH_HOST, SSH_USER
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "main.py",
    "mina_dashboard_settings.py",
    "mina_position_manager.py",
    "mina_signal_source.py",
    "mina_motor_telegram.py",
    "mina_slot_policy.py",
    "mina_tracking.py",
    "mina_signal_source.py",
    "mina_entry_orders.py",
    "mina_trading_journal.py",
    "mina_coin_lock.py",
    "mina_ssh.py",
    "mina_makro_core.py",
    "mina_makro_watcher.py",
    "mina_binance_retry.py",
    "backend/config.py",
    "scripts/reconcile_atom_derr.py",
    "backend/ghost_positions.py",
    "backend/position_manager.py",
    "signal_bot/listener.py",
    "signal_bot/haluk_message_store.py",
    "signal_bot/binance_listings.py",
    "signal_bot/binance_listings_watcher.py",
    "signal_bot/upbit_listing_reporter.py",
    "signal_bot/upbit_listing_watcher.py",
    "signal_bot/upbit_listing_trader.py",
    "signal_bot/signal_parser.py",
    "signal_bot/haluk_pdf_parser.py",
    "signal_bot/haluk_pdf_visual.py",
    "signal_bot/haluk_pdf_processed.py",
    "signal_bot/haluk_yayin_analiz.py",
    "signal_bot/macro_levels_store.py",
    "signal_bot/macro_prices.py",
    "signal_bot/signal_slot_bridge.py",
    "signal_bot/merter_dca_manager.py",
    "signal_bot/merter_dca_runner.py",
    "signal_bot/approval_bot.py",
    "signal_bot/ht_listener.py",
    "scripts/manual_open.py",
    "scripts/reconcile_derr_ghosts.py",
    "scripts/test_entry_orders.py",
    "scripts/migrate_haluk_messages.py",
    "scripts/analyze_haluk_history.py",
    "tools/telegram_bot.py",
    "dashboard/dashboard_ws.py",
    "dashboard/dashboard_auth.py",
]

SERVICES = [
    "mina-engine.service",
    "mina-listener.service",
    "mina-merter-dca.service",
    "mina-queue-watcher.service",
    "mina-dashboard-ws.service",
    "mina-dashboard-vite.service",
    "mina-binance-listings.service",
    "mina-upbit-listings.service",
    "mina-makro-watcher.service",
]


def git_sync_after_deploy(repo_root: str) -> None:
    """Deploy sonrası lokal değişiklikleri commit + push."""
    print(">>> Git sync after deploy...")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if not (status.stdout or "").strip():
        print("Git: değişiklik yok, commit atlandı")
    else:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = f"auto: deploy sonrası sync [{ts}]"
        for cmd in (
            ["git", "add", "-A"],
            ["git", "commit", "-m", msg],
        ):
            print(">>>", " ".join(cmd))
            r = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
            if r.stdout.strip():
                print(r.stdout)
            if r.stderr.strip():
                print(r.stderr)
            if r.returncode != 0 and cmd[1] == "commit":
                print("Git commit atlandı veya başarısız")
                return
    print(">>> git push origin main")
    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if push.stdout.strip():
        print(push.stdout)
    if push.stderr.strip():
        print(push.stderr)
    if push.returncode != 0:
        print(f"Git push başarısız (exit {push.returncode})")
    else:
        print("Git push OK")


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
    print(f"Connecting {HOST} (SSH key)...")
    connect_paramiko(c, host=HOST, user=USER, timeout=30)
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

    unit_local = os.path.join(LOCAL, "ops", "mina-dashboard-ws.service")
    if os.path.isfile(unit_local):
        print("PUT ops/mina-dashboard-ws.service → /etc/systemd/system/")
        sftp.put(unit_local, "/etc/systemd/system/mina-dashboard-ws.service")

    listings_unit = os.path.join(LOCAL, "ops", "mina-binance-listings.service")
    if os.path.isfile(listings_unit):
        print("PUT ops/mina-binance-listings.service → /etc/systemd/system/")
        sftp.put(listings_unit, "/etc/systemd/system/mina-binance-listings.service")

    upbit_unit = os.path.join(LOCAL, "ops", "mina-upbit-listings.service")
    if os.path.isfile(upbit_unit):
        print("PUT ops/mina-upbit-listings.service → /etc/systemd/system/")
        sftp.put(upbit_unit, "/etc/systemd/system/mina-upbit-listings.service")

    makro_unit = os.path.join(LOCAL, "ops", "mina-makro-watcher.service")
    if os.path.isfile(makro_unit):
        print("PUT ops/mina-makro-watcher.service → /etc/systemd/system/")
        sftp.put(makro_unit, "/etc/systemd/system/mina-makro-watcher.service")

    backup_local = os.path.join(LOCAL, "ops", "backup_mina.sh")
    if os.path.isfile(backup_local):
        print("PUT ops/backup_mina.sh")
        sftp.put(backup_local, f"{REMOTE}/ops/backup_mina.sh")

    env_remote = f"{REMOTE}/.env"
    try:
        with sftp.open(env_remote, "r") as f:
            env_body = f.read().decode("utf-8")
    except FileNotFoundError:
        env_body = ""
    dash_keys = ("DASHBOARD_USERNAME", "DASHBOARD_PASSWORD")
    dash_missing = [k for k in dash_keys if f"{k}=" not in env_body]
    if dash_missing:
        append = "\n# MINA Dashboard auth\nDASHBOARD_USERNAME=admin\nDASHBOARD_PASSWORD=admin\n"
        with sftp.open(env_remote, "a") as f:
            if env_body and not env_body.endswith("\n"):
                f.write("\n")
            f.write(append)
        print(f"APPEND {env_remote}: {', '.join(dash_missing)}")

    sftp.close()

    systemd_cmds = [
        f"rm -f {REMOTE}/dashboard_ws.py",
        f"sed -i 's/\\r$//' {REMOTE}/ops/backup_mina.sh 2>/dev/null || true",
        f"chmod +x {REMOTE}/ops/backup_mina.sh 2>/dev/null || true",
        "systemctl daemon-reload",
    ]

    listener_clean = (
        f"systemctl stop mina-listener.service 2>/dev/null || true; "
        f"if [ -f {REMOTE}/signal_bot/listener.lock ]; then "
        f"kill -9 $(cat {REMOTE}/signal_bot/listener.lock) 2>/dev/null || true; fi; "
        f"pkill -9 -f '{REMOTE}/venv/bin/python signal_bot/listener.py' 2>/dev/null || true; "
        f"sleep 2; rm -f {REMOTE}/signal_bot/listener.lock; "
        f"systemctl reset-failed mina-listener.service 2>/dev/null || true; "
    )

    restart_cmds = systemd_cmds + [
        f"{REMOTE}/venv/bin/pip install -q pymupdf pdfplumber yfinance 2>/dev/null || true",
        listener_clean + "systemctl restart mina-engine.service",
        "systemctl restart mina-merter-dca.service",
        "systemctl restart mina-queue-watcher.service 2>/dev/null || true",
        "systemctl start mina-listener.service",
        "systemctl restart mina-dashboard-ws.service",
        "systemctl restart mina-dashboard-vite.service",
        "systemctl enable mina-binance-listings.service 2>/dev/null || true",
        "systemctl restart mina-binance-listings.service",
        "systemctl enable mina-upbit-listings.service 2>/dev/null || true",
        "systemctl restart mina-upbit-listings.service",
        "systemctl enable mina-makro-watcher.service 2>/dev/null || true",
        "systemctl restart mina-makro-watcher.service",
        "systemctl restart mina-haluk-yayin.service 2>/dev/null || true",
        "systemctl restart mina-ht-listener.service 2>/dev/null || true",
        f"{REMOTE}/venv/bin/python {REMOTE}/scripts/test_entry_orders.py 2>&1 | tail -8",
        f"{REMOTE}/venv/bin/python {REMOTE}/scripts/reconcile_derr_ghosts.py",
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
    git_sync_after_deploy(LOCAL)


if __name__ == "__main__":
    main()
