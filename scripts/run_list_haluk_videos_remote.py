#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""list_haluk_videos.py sunucuda çalıştır."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

LOCAL = os.path.join(_ROOT, "scripts", "list_haluk_videos.py")
REMOTE = "/root/MINA_v2/scripts/list_haluk_videos.py"


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)
    try:
        sftp = client.open_sftp()
        sftp.put(LOCAL, REMOTE)
        sftp.close()
        _, stdout, stderr = client.exec_command(
            f"cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python {REMOTE}",
            timeout=600,
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        path = os.path.join(_ROOT, "haluk_video_list_run.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
            if err.strip():
                f.write("\nSTDERR:\n" + err)
        print(f"written: {path}")
        print(out)
    finally:
        client.close()


if __name__ == "__main__":
    main()
