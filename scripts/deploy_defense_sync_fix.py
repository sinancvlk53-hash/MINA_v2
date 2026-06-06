#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Deploy mina_position_manager defense sync fix."""
import os
import sys
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    rel = "mina_position_manager.py"
    sftp.put(os.path.join(LOCAL, rel), f"{REMOTE}/{rel}")
    print(f">>> PUT {rel}")
    sftp.close()

    cmd = (
        f"systemctl restart mina-engine.service && "
        f"sleep 3 && "
        f"systemctl is-active mina-engine.service && "
        f"journalctl -u mina-engine.service -n 25 --no-pager | "
        f"grep -E 'defense_preserved|defense_level|BCHUSDT|BOOTSTRAP|SYNC' || "
        f"journalctl -u mina-engine.service -n 15 --no-pager"
    )
    print(">>> restart mina-engine.service")
    _, out, err = c.exec_command(cmd, timeout=90)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("stderr:", e)
    c.close()
    print(">>> Deploy tamamlandı.")


if __name__ == "__main__":
    main()
