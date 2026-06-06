
import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=15)
_, out, err = c.exec_command(
    "grep -E 'ERROR|CRITICAL' /root/MINA_v2/mina_bot.log | tail -n 10",
    timeout=120,
)
sys.stdout.write(out.read().decode("utf-8", errors="replace"))
e = err.read().decode("utf-8", errors="replace")
if e:
    sys.stdout.write("STDERR: " + e)
c.close()
