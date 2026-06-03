#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deploy sonrası DERR + engine.lock doğrulama."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"

VERIFY = r'''
cd /root/MINA_v2 && venv/bin/python - <<'PY'
import sqlite3
conn = sqlite3.connect("mina_trading_journal.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
SELECT symbol, side, status, close_time, close_reason, pnl_usdt
FROM trades ORDER BY created_at DESC LIMIT 15
""")
print("=== SQL trades (last 15) ===")
for r in cur.fetchall():
    print("|".join(str(r[k]) if r[k] is not None else "" for k in r.keys()))
cur.execute("SELECT COUNT(*) FROM trades WHERE status='closed'")
print("CLOSED_COUNT:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM trades WHERE status='open'")
print("OPEN_COUNT:", cur.fetchone()[0])
conn.close()
PY
echo "=== engine.lock ==="
cat /root/MINA_v2/engine.lock
echo ""
PID=$(cat /root/MINA_v2/engine.lock 2>/dev/null)
ps -p "$PID" -o pid,cmd,etime 2>&1 || echo "pid not running: $PID"
systemctl is-active mina-engine.service
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    _, out, err = c.exec_command(VERIFY, timeout=40)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()


if __name__ == "__main__":
    main()
