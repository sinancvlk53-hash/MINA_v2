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
for remote, local in [
    ("/root/MINA_v2/signal_bot/history/haluk_video_list.json", os.path.join(_ROOT, "signal_bot/history/haluk_video_list.json")),
    ("/root/MINA_v2/signal_bot/history/haluk_video_list.md", os.path.join(_ROOT, "signal_bot/history/haluk_video_list.md")),
]:
    os.makedirs(os.path.dirname(local), exist_ok=True)
    sftp.get(remote, local)
    print("downloaded", local)
sftp.close()
c.close()
