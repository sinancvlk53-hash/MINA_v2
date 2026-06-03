#!/usr/bin/env python3
import json
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", "root", password=os.environ.get("MINA_SSH_PASS", "REDACTED"), timeout=20)
cmds = [
    "pgrep -af queue_watcher || echo NO_WATCHER",
    "pgrep -af 'signal_bot/listener.py' | head -2",
    "systemctl is-active mina-listener 2>/dev/null",
    "tail -8 /root/MINA_v2/signal_bot/pipeline_audit.log 2>/dev/null || true",
    "sqlite3 /root/MINA_v2/mina_trading_journal.db \"SELECT COUNT(*) FROM sqlite_master WHERE name='signal_decisions';\" 2>/dev/null",
]
for cmd in cmds:
    print("---", cmd[:60])
    _, o, _ = c.exec_command(cmd, timeout=15)
    print(o.read().decode())
sftp = c.open_sftp()
try:
    with sftp.open("/root/MINA_v2/signal_bot/raw_signal_queue.json") as f:
        q = json.loads(f.read().decode())
    entries = q.get("entries") or []
    print("--- queue")
    print("updated_at:", q.get("updated_at"))
    print("entries:", len(entries), "merter:", sum(1 for x in entries if x.get("source") == "merter"))
except Exception as ex:
    print("queue read err:", ex)
c.close()
