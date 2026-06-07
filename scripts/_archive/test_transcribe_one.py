#!/usr/bin/env python3
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
cmd = (
    "cd /root/MINA_v2 && "
    "cp -f session_ht.session session_ht_bulk.session; "
    "/root/MINA_v2/venv/bin/python -u /root/MINA_v2/scripts/transcribe_all_haluk_videos.py --limit 1 "
    "2>&1 | tail -30"
)
_, o, e = c.exec_command(cmd, timeout=300)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
path = os.path.join(_ROOT, "transcribe_test_out.txt")
with open(path, "w", encoding="utf-8") as f:
    f.write(out)
    if err:
        f.write("\nERR:\n" + err)
print("written", path)
print(out[-3000:] if len(out) > 3000 else out)
c.close()
