#!/usr/bin/env python3
"""One-off: run journal queries on MINA server via SSH."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paramiko
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

REMOTE = r"""
cd /root/MINA_v2

echo "========== 1. Son 12 saatte acilan pozisyonlar =========="
python3 << 'PY1'
import sqlite3
from datetime import datetime, timedelta
conn = sqlite3.connect('mina_trading_journal.db')
since = (datetime.utcnow() - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
rows = conn.execute('''
    SELECT symbol, side, leverage, open_price, open_qty,
           open_time, status, signal_source, pnl_usdt, close_reason
    FROM trades WHERE open_time > ? ORDER BY open_time DESC
''', (since,)).fetchall()
print(f'Toplam: {len(rows)}')
for r in rows:
    print(r)
conn.close()
PY1

echo ""
echo "========== 2. Defense tetiklenenler =========="
python3 << 'PY2'
import sqlite3
from datetime import datetime, timedelta
conn = sqlite3.connect('mina_trading_journal.db')
since = (datetime.utcnow() - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
rows = conn.execute('''
    SELECT symbol, side, open_price, defense_triggered,
           defense_prices, open_time, status, pnl_usdt
    FROM trades
    WHERE open_time > ? AND defense_triggered IS NOT NULL
    AND defense_triggered != 0
    ORDER BY open_time DESC
''', (since,)).fetchall()
print(f'Defense tetiklenen: {len(rows)}')
for r in rows:
    print(r)
conn.close()
PY2

echo ""
echo "========== 3. TP / Kapanan islemler =========="
python3 << 'PY3'
import sqlite3
from datetime import datetime, timedelta
conn = sqlite3.connect('mina_trading_journal.db')
since = (datetime.utcnow() - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
rows = conn.execute('''
    SELECT symbol, side, open_price, close_price,
           pnl_usdt, pnl_percent, close_reason, open_time, close_time
    FROM trades
    WHERE open_time > ? AND status = "closed"
    ORDER BY close_time DESC
''', (since,)).fetchall()
print(f'Kapanan: {len(rows)}')
for r in rows:
    print(r)
conn.close()
PY3

echo ""
echo "========== 4a. mina_bot.log son hatalar =========="
grep -i "error\|hata\|fail\|exception" /root/MINA_v2/mina_bot.log 2>/dev/null | tail -30 || echo "(log yok veya eslesme yok)"

echo ""
echo "========== 4b. journalctl mina-engine =========="
journalctl -u mina-engine -n 20 --no-pager 2>/dev/null || echo "(servis yok)"

echo ""
echo "========== 4c. journalctl mina-pdf-listener =========="
journalctl -u mina-pdf-listener -n 10 --no-pager 2>/dev/null || echo "(servis yok)"

echo ""
echo "========== 4d. journalctl mina-ht-listener =========="
journalctl -u mina-ht-listener -n 10 --no-pager 2>/dev/null || echo "(servis yok)"

echo ""
echo "========== 5. position_states.json =========="
cat /root/MINA_v2/position_states.json 2>/dev/null || echo "(dosya yok)"
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
