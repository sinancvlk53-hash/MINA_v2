#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE_SCRIPT = r'''
echo "========== 1) sabah_kontrol.py =========="
/root/MINA_v2/venv/bin/python /root/MINA_v2/scripts/sabah_kontrol.py 2>&1

echo ""
echo "========== 2) mina_bot.log tail -50 =========="
tail -50 /root/MINA_v2/mina_bot.log 2>/dev/null || echo "(log yok)"

echo ""
echo "========== 3) merter_dca.log tail -30 =========="
tail -30 /root/MINA_v2/signal_bot/merter_dca.log 2>/dev/null || echo "(log yok)"

echo ""
echo "========== 4) servis durumları =========="
systemctl is-active mina-engine mina-merter-dca mina-listener mina-queue-watcher mina-dashboard-ws mina-dashboard-vite mina-haluk-yayin 2>&1
'''


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_SCRIPT, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        path = os.path.join(_ROOT, "report_12h_out.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
            if err.strip():
                f.write("\nSTDERR:\n" + err)
        print(path)
    finally:
        client.close()


if __name__ == "__main__":
    main()
