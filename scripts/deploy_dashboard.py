#!/usr/bin/env python3
"""Deploy dashboard dist/ to production server."""
import os
import paramiko

HOST, USER, PASS = "178.105.150.40", "root", "REDACTED"
REMOTE = "/root/MINA_v2/dashboard/dist"
LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "dist")


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
    ensure_remote_dir(sftp, REMOTE)

    for root, _, files in os.walk(LOCAL):
        rel = os.path.relpath(root, LOCAL).replace("\\", "/")
        remote_dir = REMOTE if rel == "." else f"{REMOTE}/{rel}"
        ensure_remote_dir(sftp, remote_dir)
        for f in files:
            lp = os.path.join(root, f)
            rp = f"{remote_dir}/{f}"
            print("PUT", rp)
            sftp.put(lp, rp)

    for cmd in (
        "systemctl restart mina-dashboard-vite.service",
        "systemctl is-active mina-dashboard-vite.service",
        'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/',
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
