#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)
sftp = c.open_sftp()
files = [
    ("signal_bot/history/haluk_video_list.json", "/root/MINA_v2/signal_bot/history/haluk_video_list.json"),
    ("signal_bot/history/haluk_video_list.md", "/root/MINA_v2/signal_bot/history/haluk_video_list.md"),
    ("signal_bot/haluk_video_categories.py", "/root/MINA_v2/signal_bot/haluk_video_categories.py"),
    ("scripts/recategorize_haluk_videos.py", "/root/MINA_v2/scripts/recategorize_haluk_videos.py"),
]
for local_rel, remote in files:
    local = os.path.join(_ROOT, local_rel.replace("/", os.sep))
    sftp.put(local, remote)
    print("uploaded", remote)
sftp.close()
c.close()
