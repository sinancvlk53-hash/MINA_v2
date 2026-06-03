#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DERR journal — sunucuda dün gece kapanan işlemler."""
import os
import sys

import paramiko

HOST = "178.105.150.40"
USER = "root"
REMOTE = "/root/MINA_v2"

# Şifre ortam değişkeninden veya deploy script ile aynı (repo içi)
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")

QUERY = r'''
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python - <<'PY'
import sqlite3, os
from datetime import datetime, timedelta

paths = [
    "/root/MINA_v2/mina_trading_journal.db",
    "/root/MINA_v2/data/mina_trading_journal.db",
]
db = next((p for p in paths if os.path.isfile(p)), None)
print("DB:", db or "BULUNAMADI")
if not db:
    raise SystemExit(0)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# dün gece: son 18 saat (gece kapanışları için geniş pencere)
since = (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute(
    """SELECT id, symbol, side, leverage, close_time, close_reason, pnl_usdt, status
       FROM trades
       WHERE status = 'closed' AND close_time >= ?
       ORDER BY close_time DESC""",
    (since,),
)
rows = cur.fetchall()
print("KAPANAN_SAYI_18H:", len(rows))
for r in rows:
    print(dict(r))

cur.execute("SELECT COUNT(*) FROM trades WHERE status='open'")
print("ACIK_KAYIT:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM trades WHERE status='closed'")
print("TOPLAM_KAPALI:", cur.fetchone()[0])
print("--- SON 12 KAYIT ---")
cur.execute(
    "SELECT id, symbol, side, status, open_time, close_time, close_reason FROM trades ORDER BY id DESC LIMIT 12"
)
for r in cur.fetchall():
    print(dict(r))
conn.close()
PY
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    _, out, err = c.exec_command(QUERY, timeout=30)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e, file=sys.stderr)
    c.close()


if __name__ == "__main__":
    main()
