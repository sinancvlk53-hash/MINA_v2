#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)

cmd = r"grep -E 'XRPUSDT|AVAXUSDT|BCHUSDT|BNBUSDT' /root/MINA_v2/mina_bot.log 2>&1"
_, out, err = c.exec_command(cmd, timeout=180)
data = out.read().decode("utf-8", errors="replace")
errdata = err.read().decode("utf-8", errors="replace")

print(data if data else "(bos cikti)")
if errdata.strip():
    print("stderr:", errdata)
print("---")
print("satir sayisi:", len(data.splitlines()) if data else 0)
c.close()
