#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""pdf_listener.service durdur + devre dışı; MINA aktif servisleri listele."""
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()

UNITS = [
    "mina-listener",
    "mina-ht-listener",
    "mina-pdf-listener",
    "mina-engine",
    "mina-dashboard-ws",
    "mina-dashboard-vite",
]


def run(c, cmd: str) -> str:
    _, out, err = c.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    return o + (f"\n{e}" if e.strip() else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)

    print(">>> PDF listener unit aranıyor")
    units = run(c, "systemctl list-unit-files --no-pager | grep -i pdf").strip()
    print(units or "(systemd unit yok)")
    for name in ("pdf_listener.service", "mina-pdf-listener.service"):
        print(f">>> stop/disable {name}")
        print(run(c, f"systemctl stop {name} 2>&1; systemctl disable {name} 2>&1"))
    print(run(c, "pkill -9 -f signal_bot/pdf_listener.py 2>/dev/null; sleep 1; true"))

    print("\n=== PDF LISTENER ===")
    print(run(c, "systemctl is-active pdf_listener.service; systemctl is-enabled pdf_listener.service"))

    print("=== MINA SERVISLERI (çalışan) ===")
    print(
        run(
            c,
            "systemctl list-units --type=service --state=running "
            "| grep -iE 'mina|pdf|listener|engine|dashboard' || echo '(eşleşme yok)'",
        )
    )

    print("=== TÜM MINA UNIT DURUMLARI ===")
    for u in UNITS:
        active = run(c, f"systemctl is-active {u}.service 2>/dev/null").strip()
        enabled = run(c, f"systemctl is-enabled {u}.service 2>/dev/null").strip()
        print(f"  {u:28} active={active:12} enabled={enabled}")

    print("\n=== LISTENER PROCESSES ===")
    print(run(c, "pgrep -af 'signal_bot/(listener|ht_listener|pdf_listener)' || echo '(yok)'"))

    c.close()


if __name__ == "__main__":
    main()
