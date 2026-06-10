#!/usr/bin/env python3
"""HT listener lock fix + SOL journal query on remote server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paramiko
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

REMOTE = r"""
echo "========== Lock dosyasi =========="
cat /root/MINA_v2/signal_bot/ht_listener.lock 2>/dev/null || echo "(lock yok)"

echo ""
echo "========== PID 826141 =========="
ps aux | grep 826141 | grep -v grep || echo "PID 826141 bulunamadi"

echo ""
echo "========== ht_listener processleri =========="
ps aux | grep ht_listener | grep -v grep || echo "(ht_listener process yok)"

LOCK_PID=$(cat /root/MINA_v2/signal_bot/ht_listener.lock 2>/dev/null | tr -d '[:space:]')
if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
  echo ""
  echo "Lock PID $LOCK_PID CALISIYOR -> systemd durdur, lock sil, yeniden baslat"
  systemctl stop mina-ht-listener 2>/dev/null || true
  sleep 1
  # Eski orphan process varsa oldur
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    kill "$LOCK_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$LOCK_PID" 2>/dev/null || true
  fi
  rm -f /root/MINA_v2/signal_bot/ht_listener.lock
  systemctl start mina-ht-listener
  sleep 3
  systemctl status mina-ht-listener --no-pager
elif [ -n "$LOCK_PID" ]; then
  echo ""
  echo "Lock PID $LOCK_PID OLUMLU -> stale lock sil, servis baslat"
  rm -f /root/MINA_v2/signal_bot/ht_listener.lock
  systemctl restart mina-ht-listener
  sleep 3
  systemctl status mina-ht-listener --no-pager
else
  echo ""
  echo "Lock yok -> servis durumu:"
  systemctl status mina-ht-listener --no-pager 2>/dev/null || true
fi

echo ""
echo "========== SOL journal =========="
cd /root/MINA_v2 && python3 << 'PY'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[0] for d in conn.execute('PRAGMA table_info(trades)').fetchall()]
rows = conn.execute("SELECT * FROM trades WHERE symbol='SOLUSDT' ORDER BY open_time DESC LIMIT 2").fetchall()
for r in rows:
    for c, v in zip(cols, r):
        print(f'{c}: {v}')
    print('---')
conn.close()
PY

echo ""
echo "========== defense grep (remote) =========="
grep -n "defense_triggered\|defense_prices\|log_defense\|journal" /root/MINA_v2/mina_position_manager.py | head -30
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c, host=SSH_HOST, user=SSH_USER, timeout=30)
    _, stdout, stderr = c.exec_command(REMOTE, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stderr.buffer.write(("STDERR: " + err).encode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
