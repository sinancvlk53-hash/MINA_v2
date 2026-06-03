#!/usr/bin/env python3
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", "root", password=os.environ.get("MINA_SSH_PASS", "REDACTED"), timeout=20)

cmds = [
    "journalctl -u mina-listener.service -n 30 --no-pager",
    "ls -la /root/MINA_v2/signal_bot/listener.lock 2>&1 || true",
    "cd /root/MINA_v2 && venv/bin/python -c 'from signal_bot.signal_parser import parse_merter; print(\"import_ok\")'",
    "systemctl is-active mina-listener.service; systemctl is-active mina-queue-watcher.service",
]
for cmd in cmds:
    print("===", cmd, "===")
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    er = e.read().decode("utf-8", errors="replace")
    if er.strip():
        print("ERR:", er)
c.close()
