#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
lines = []
for cmd in [
    "ls /root/MINA_v2/signal_bot/history/transcripts | wc -l",
    "tail -5 /root/MINA_v2/signal_bot/history/transcribe_all.log",
]:
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    lines.append(f"$ {cmd}\n{out}")
    if err.strip():
        lines.append(err)
c.close()
with open(os.path.join(_ROOT, "transcribe_progress_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
