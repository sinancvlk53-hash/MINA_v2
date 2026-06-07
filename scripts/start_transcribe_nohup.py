#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
transport = c.get_transport()
channel = transport.open_session()
channel.exec_command(
    "bash -lc 'cd /root/MINA_v2 && "
    "cp -f session_ht.session session_ht_bulk.session 2>/dev/null; "
    "cp -f session_ht.session-journal session_ht_bulk.session-journal 2>/dev/null; "
    "mkdir -p signal_bot/history/transcripts; "
    "nohup /root/MINA_v2/venv/bin/python -u /root/MINA_v2/scripts/transcribe_all_haluk_videos.py "
    ">> /root/MINA_v2/signal_bot/history/transcribe_all.log 2>&1 &'"
)
channel.close()
c.close()
print("transcribe started in background (detached)")
