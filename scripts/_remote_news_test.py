#!/usr/bin/env python3
import paramiko
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c, host=SSH_HOST, user=SSH_USER, timeout=30)
cmds = [
    """cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
import requests
print('requests OK:', requests.__version__)
from mina_motor_telegram import send_telegram
print('mina_motor_telegram OK')
" """,
    """cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import sys
sys.path.insert(0, '/root/MINA_v2')
from signal_bot.news_watcher import run_news_watcher
result = run_news_watcher()
print('Sonuç:', result)
" """,
]
for cmd in cmds:
    print("=" * 60)
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("ERR:", err)
c.close()
