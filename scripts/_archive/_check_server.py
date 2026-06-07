
import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko, os, time

HOST = SSH_HOST
USER = SSH_USER
PASS = require_ssh_pass()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=10)

cmds = [
    ("backtest.py var mi?",    "ls -lh /root/MINA_v2/backtest.py 2>&1"),
    ("ei_signals.json var mi?","ls -lh /root/MINA_v2/signal_bot/history/ei_signals.json 2>&1"),
    ("Python calisiyor mu?",   "pgrep -a python 2>&1"),
    ("backtest.log",           "cat /tmp/backtest.log 2>&1 | tail -10"),
]

for label, cmd in cmds:
    _, out, _ = c.exec_command(cmd)
    result = out.read().decode().strip()
    print(f"\n[{label}]\n{result}")

c.close()
