#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
cmds = [
    "pgrep -af transcribe_all_haluk_videos.py",
    "ls /root/MINA_v2/signal_bot/history/transcripts 2>/dev/null | wc -l",
    "tail -15 /root/MINA_v2/signal_bot/history/transcribe_all.log 2>/dev/null || echo 'no log yet'",
    "systemctl is-active mina-haluk-yayin.service",
    "/root/MINA_v2/venv/bin/python -c \"from signal_bot.haluk_predictions import init_predictions_table; init_predictions_table(); import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); print([r[0] for r in c.execute(\\\"SELECT name FROM sqlite_master WHERE name LIKE 'haluk%'\\\")])\"",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(">>>", cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
