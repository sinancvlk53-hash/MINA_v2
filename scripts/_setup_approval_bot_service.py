#!/usr/bin/env python3
"""Deploy mina-approval-bot.service, start, wait, verify queue + positions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paramiko
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

LOCAL_SERVICE = Path(__file__).resolve().parents[1] / "ops" / "mina-approval-bot.service"

REMOTE = r"""
rm -f /root/MINA_v2/signal_bot/approval_bot.lock
pkill -f '/root/MINA_v2/signal_bot/approval_bot.py' 2>/dev/null || true
sleep 1
systemctl daemon-reload
systemctl enable mina-approval-bot
systemctl restart mina-approval-bot
sleep 2
systemctl status mina-approval-bot --no-pager | head -20

echo ""
echo "========== 30 sn bekleniyor =========="
sleep 30

echo ""
echo "========== ht_signals_queue.json =========="
if [ -f /root/MINA_v2/signal_bot/ht_signals_queue.json ]; then
  python3 -m json.tool /root/MINA_v2/signal_bot/ht_signals_queue.json
else
  echo "(dosya silindi / yok — kuyruk tüketilmiş olabilir)"
fi

echo ""
echo "========== journalctl son 15 satir =========="
journalctl -u mina-approval-bot -n 15 --no-pager 2>/dev/null || true

echo ""
echo "========== Binance pozisyonlar =========="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
print(f'Acik: {len(positions)}')
for p in positions:
    print(p['symbol'], p['positionAmt'], p['unrealizedProfit'])
PY
"""


def main():
    print(f"Upload: {LOCAL_SERVICE}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c, host=SSH_HOST, user=SSH_USER, timeout=30)

    sftp = c.open_sftp()
    print(f"PUT {LOCAL_SERVICE} -> /etc/systemd/system/mina-approval-bot.service")
    sftp.put(str(LOCAL_SERVICE), "/etc/systemd/system/mina-approval-bot.service")
    approval_py = Path(__file__).resolve().parents[1] / "signal_bot" / "approval_bot.py"
    print(f"PUT {approval_py} -> /root/MINA_v2/signal_bot/approval_bot.py")
    sftp.put(str(approval_py), "/root/MINA_v2/signal_bot/approval_bot.py")
    sftp.close()

    _, stdout, stderr = c.exec_command(REMOTE, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stderr.buffer.write(("STDERR: " + err).encode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
