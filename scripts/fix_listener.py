#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""mina-listener teşhis + düzelt + restart."""
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"

DIAG = """
echo '=== systemctl status ==='
systemctl status mina-listener.service --no-pager -l 2>&1 | head -25
echo ''
echo '=== journalctl (son 40) ==='
journalctl -u mina-listener.service -n 40 --no-pager 2>&1
echo ''
echo '=== listener.lock ==='
cat /root/MINA_v2/signal_bot/listener.lock 2>/dev/null || echo '(yok)'
ls -la /root/MINA_v2/signal_bot/listener.lock 2>/dev/null || true
echo ''
echo '=== unit file ==='
cat /etc/systemd/system/mina-listener.service 2>/dev/null || echo '(yok)'
echo ''
echo '=== listener prosesleri ==='
pgrep -af 'listener.py' || echo '(yok)'
"""

FIX = f"""
cd {REMOTE}
systemctl stop mina-listener.service 2>/dev/null
pkill -9 -f 'signal_bot/listener.py' 2>/dev/null || true
sleep 1
rm -f signal_bot/listener.lock
# Import test
{REMOTE}/venv/bin/python -c "
import sys
sys.path.insert(0, '{REMOTE}')
from dotenv import load_dotenv
load_dotenv('{REMOTE}/.env')
from signal_bot.listener import _validate_config
_validate_config()
print('CONFIG_OK')
" 2>&1
"""

RESTART = f"""
cd {REMOTE}
systemctl stop mina-listener.service 2>/dev/null
pkill -9 -f 'signal_bot/listener.py' 2>/dev/null || true
sleep 2
rm -f signal_bot/listener.lock
systemctl reset-failed mina-listener.service 2>/dev/null || true
systemctl start mina-listener.service
sleep 6
systemctl is-active mina-listener.service
systemctl status mina-listener.service --no-pager -l 2>&1 | head -15
journalctl -u mina-listener.service -n 8 --no-pager 2>&1
pgrep -af 'signal_bot/listener.py' || echo 'NO_PROCESS'
tail -5 /root/MINA_v2/signal_bot/signals_log.txt 2>/dev/null || echo 'no signals_log'
"""

def run(c, script, title, timeout=90):
    print("=" * 70)
    print(title)
    print("=" * 70)
    _, out, err = c.exec_command(script, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace")
    print(o if o.strip() else "(boş çıktı)")
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("stderr:", e)
    return o

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signal_bot", "listener.py")
    print(">>> PUT signal_bot/listener.py (stale lock fix)")
    sftp.put(local, f"{REMOTE}/signal_bot/listener.py")
    sftp.close()
    run(c, DIAG, "TEŞHİS")
    run(c, FIX, "DÜZELTME (stop, lock, import test)")
    run(c, RESTART, "RESTART (stop → kill → start)", timeout=120)
    run(c, "sleep 12; systemctl is-active mina-listener; pgrep -af signal_bot/listener.py; cat /root/MINA_v2/signal_bot/listener.lock 2>/dev/null; tail -8 /root/MINA_v2/signal_bot/signals_log.txt", "12sn sonra doğrulama", timeout=30)
    c.close()
    print("=" * 70)
    print("BİTTİ")

if __name__ == "__main__":
    main()
