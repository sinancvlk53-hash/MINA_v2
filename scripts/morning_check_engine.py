#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")

CMD = """
echo '=== systemd ==='
systemctl is-active mina-engine.service 2>&1
systemctl status mina-engine.service --no-pager -l 2>&1 | head -12
echo '=== process ==='
pgrep -af 'python.*main.py' || echo 'main.py yok'
echo '=== engine.lock ==='
cat /root/MINA_v2/engine.lock 2>&1 || echo 'lock yok'
ls -la /root/MINA_v2/engine.lock 2>&1
echo '=== lock pid alive? ==='
if [ -f /root/MINA_v2/engine.lock ]; then
  pid=$(cat /root/MINA_v2/engine.lock)
  ps -p $pid -o pid,cmd,etime 2>&1 || echo "pid $pid yok"
fi
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    _, out, err = c.exec_command(CMD, timeout=20)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()


if __name__ == "__main__":
    main()
