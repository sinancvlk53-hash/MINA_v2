#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import json
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, SSH_USER, password=require_ssh_pass(), timeout=20)
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
