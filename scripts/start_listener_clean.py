#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, sys, time, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"

CMD = f"""
systemctl stop mina-listener.service 2>/dev/null || true
pkill -9 -f 'signal_bot/listener.py' 2>/dev/null || true
sleep 2
rm -f {REMOTE}/signal_bot/listener.lock
systemctl reset-failed mina-listener.service 2>/dev/null || true
systemctl start mina-listener.service
sleep 8
echo "=== STATUS ==="
systemctl is-active mina-listener.service
systemctl show mina-listener.service -p MainPID,ActiveState,SubState --no-pager
echo "=== PROCESSES ==="
pgrep -af 'signal_bot/listener.py' || echo NONE
echo "=== LOCK ==="
cat {REMOTE}/signal_bot/listener.lock 2>/dev/null || echo no_lock
echo "=== LOG TAIL ==="
tail -6 {REMOTE}/signal_bot/signals_log.txt
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=25)
stdin, stdout, stderr = c.exec_command(CMD, timeout=60)
exit_code = stdout.channel.recv_exit_status()
text = stdout.read().decode("utf-8", errors="replace")
print(text if text.strip() else f"(boş çıktı, exit={exit_code})")
e = stderr.read().decode("utf-8", errors="replace")
if e.strip():
    print("stderr:", e)
c.close()
