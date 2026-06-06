#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Deploy dashboard dist/ + WS backend to production server."""
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
ROOT = "/root/MINA_v2"
REMOTE_DIST = f"{ROOT}/dashboard/dist"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DIST = os.path.join(LOCAL_ROOT, "dashboard", "dist")
LOCAL_WS = os.path.join(LOCAL_ROOT, "dashboard", "dashboard_ws.py")


def ensure_remote_dir(sftp, path):
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sftp = c.open_sftp()
    ensure_remote_dir(sftp, REMOTE_DIST)

    sftp.put(LOCAL_WS, f"{ROOT}/dashboard/dashboard_ws.py")
    print("PUT dashboard/dashboard_ws.py")

    for root, _, files in os.walk(LOCAL_DIST):
        rel = os.path.relpath(root, LOCAL_DIST).replace("\\", "/")
        remote_dir = REMOTE_DIST if rel == "." else f"{REMOTE_DIST}/{rel}"
        ensure_remote_dir(sftp, remote_dir)
        for f in files:
            lp = os.path.join(root, f)
            rp = f"{remote_dir}/{f}"
            print("PUT", rp)
            sftp.put(lp, rp)

    sftp.close()

    for cmd in (
        "systemctl restart mina-dashboard-ws.service",
        "systemctl restart mina-dashboard-vite.service",
        "sleep 2",
        "systemctl is-active mina-dashboard-ws.service mina-dashboard-vite.service",
        'curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:3000/',
    ):
        print(">>>", cmd)
        _, out, err = c.exec_command(cmd, timeout=30)
        o = out.read().decode().strip()
        e = err.read().decode().strip()
        if o:
            print(o)
        if e:
            print("ERR:", e)

    c.close()
    print("DONE")


if __name__ == "__main__":
    main()
