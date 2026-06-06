#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""11-18 sağlık raporu — state sync + lokal çalıştır."""
import os
import subprocess
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(LOCAL_ROOT, ".mina_health_cache")
REMOTE = "/root/MINA_v2"

SYNC_PATHS = [
    "mina_trading_journal.db",
    "mina_bot.log",
    "signals_log.txt",
    "defense_levels.json",
    "initial_entry_prices.json",
    "initial_margins.json",
    "position_sources.json",
    "signal_bot/merter_dca_state.json",
    "signal_bot/raw_signal_queue.json",
    "signal_bot/macro_levels.json",
    ".env",
]


def sync_from_server() -> None:
    os.makedirs(CACHE, exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()
    for rel in SYNC_PATHS:
        local = os.path.join(CACHE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(local), exist_ok=True)
        try:
            sftp.get(f"{REMOTE}/{rel}", local)
        except FileNotFoundError:
            pass
    c.close()


def main() -> None:
    script = os.path.join(LOCAL_ROOT, "scripts", "health_report_11_18.py")
    out_path = os.path.join(LOCAL_ROOT, "health_11_18_out.txt")
    sync_from_server()
    env = os.environ.copy()
    env["MINA_DATA_ROOT"] = CACHE
    proc = subprocess.run(
        [sys.executable, script],
        cwd=LOCAL_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")
        if proc.stderr:
            f.write("\n--- stderr ---\n")
            f.write(proc.stderr)
    print(f"Written to {out_path} exit={proc.returncode}")


if __name__ == "__main__":
    main()
