#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acil: dashboard http.server'a geri don + servis restart."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"
LOCAL_UNIT = os.path.join(_ROOT, "ops", "mina-dashboard-vite.service")


def run(client, cmd: str, timeout: int = 30) -> str:
    print(">>>", cmd)
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("ERR:", err)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pwd = require_ssh_pass()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)

    print("=== ONCE (teşhis) ===")
    run(c, "systemctl is-active mina-dashboard-vite.service || true")
    run(c, "tail -20 /root/MINA_v2/vite_dashboard.log 2>/dev/null || true")
    run(c, 'curl -s -o /dev/null -w "HTTP %{http_code}\\n" --max-time 5 http://127.0.0.1:3000/ || echo FAIL')

    print("\n=== GERI AL: http.server ===")
    sftp = c.open_sftp()
    sftp.put(LOCAL_UNIT, "/etc/systemd/system/mina-dashboard-vite.service")
    sftp.close()
    print("PUT ops/mina-dashboard-vite.service")

    for cmd in (
        "systemctl daemon-reload",
        "systemctl restart mina-dashboard-vite.service",
        "sleep 2",
        "systemctl is-active mina-dashboard-vite.service",
        "ss -tlnp | grep ':3000' || true",
        'curl -s -o /dev/null -w "HTTP %{http_code}\\n" --max-time 5 http://127.0.0.1:3000/',
        "curl -s --max-time 5 http://127.0.0.1:3000/ | head -5",
    ):
        run(c, cmd)

    c.close()
    print("\nDASHBOARD FIX DONE")


if __name__ == "__main__":
    main()
