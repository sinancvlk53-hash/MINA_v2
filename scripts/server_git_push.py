#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Sunucuda git push dene (SSH key veya token)."""
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"


def run(c, cmd):
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(err)
    return out + err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    run(c, "ls -la ~/.ssh 2>/dev/null || true")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        run(
            c,
            f'cd {REMOTE} && git push https://x-access-token:{token}@github.com/sinancvlk53-hash/MINA_v2.git HEAD:main',
        )
    else:
        run(c, f"cd {REMOTE} && git remote set-url origin git@github.com:sinancvlk53-hash/MINA_v2.git")
        run(c, f"cd {REMOTE} && GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new' git push origin HEAD:main 2>&1")
    run(c, f"cd {REMOTE} && git log -1 --oneline")
    c.close()


if __name__ == "__main__":
    main()
