
import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=10)

_, out, _ = c.exec_command("cat /tmp/backtest.log")
print(out.read().decode())

# backtest_results.json indir
sftp = c.open_sftp()
sftp.get("/root/MINA_v2/signal_bot/history/backtest_results.json",
         "signal_bot/history/backtest_results.json")
sftp.close()
print("backtest_results.json indirildi.")
c.close()
