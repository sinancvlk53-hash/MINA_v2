#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""mina-dashboard-ws.service deploy — ops/mina-dashboard-ws.service kullanır."""
import os
import sys
import time

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIT_LOCAL = os.path.join(LOCAL, "ops", "mina-dashboard-ws.service")
SERVICE = "/etc/systemd/system/mina-dashboard-ws.service"
REMOTE_ROOT_WS = "/root/MINA_v2/dashboard_ws.py"


def run(c, cmd, timeout=60):
    print(f">>> {cmd}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(err, file=sys.stderr)
    return out + err


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()
    sftp.put(UNIT_LOCAL, SERVICE)
    sftp.close()

    run(c, f"rm -f {REMOTE_ROOT_WS}")

    run(c, "systemctl daemon-reload")
    run(c, "systemctl restart mina-dashboard-ws.service")
    time.sleep(3)
    run(c, "systemctl is-active mina-dashboard-ws.service")
    run(c, "systemctl cat mina-dashboard-ws.service | grep ExecStart")
    run(c, "ps aux | grep dashboard_ws | grep -v grep")
    c.close()
    print("Service updated and restarted.")


if __name__ == "__main__":
    main()
