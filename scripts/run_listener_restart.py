#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()

STEPS = [
    "systemctl stop mina-listener.service 2>/dev/null || true",
    "if [ -f /root/MINA_v2/signal_bot/listener.lock ]; then kill -9 $(cat /root/MINA_v2/signal_bot/listener.lock) 2>/dev/null; fi",
    "pkill -9 -f '/root/MINA_v2/venv/bin/python signal_bot/listener.py' 2>/dev/null || true",
    "sleep 2",
    "rm -f /root/MINA_v2/signal_bot/listener.lock",
    "systemctl reset-failed mina-listener.service 2>/dev/null || true",
    "systemctl start mina-listener.service",
    "sleep 6",
    "systemctl is-active mina-listener.service",
    "tail -8 /root/MINA_v2/signal_bot/signals_log.txt",
]


def run_step(c, cmd):
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip() or err.strip():
        print(out.rstrip())
        if err.strip():
            print(err.rstrip(), file=sys.stderr)


def main():
    last_err = None
    for attempt in range(1, 4):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, username=USER, password=PASS, timeout=25)
            for cmd in STEPS:
                if cmd.startswith("sleep"):
                    time.sleep(int(cmd.split()[-1]))
                    continue
                run_step(c, cmd)
            c.close()
            return
        except OSError as e:
            last_err = e
            print(f"deneme {attempt}: {e}")
            time.sleep(2)
    print(f"SSH bağlanılamadı: {last_err}")
    sys.exit(1)


if __name__ == "__main__":
    main()
