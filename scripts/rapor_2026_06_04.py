#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4 Haziran 2026 tam rapor — ham çıktılar."""
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"

REMOTE_PY = REMOTE + "/scripts/_rapor_derr_query.py"

LOCAL_QUERY = '''#!/usr/bin/env python3
import sqlite3
DB = "/root/MINA_v2/mina_trading_journal.db"

def q(sql):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        return cur.execute(sql).fetchall()
    finally:
        con.close()

print("=" * 80)
print("2) DERR — bugün kapanan işlemler")
print("=" * 80)
rows = q("""
SELECT symbol, side, close_reason, pnl_usdt, close_time
FROM trades
WHERE date(close_time)='2026-06-04'
""")
if not rows:
    print("(kayıt yok)")
else:
    cols = ["symbol", "side", "close_reason", "pnl_usdt", "close_time"]
    print("  ".join(f"{c:>14}" for c in cols))
    for r in rows:
        print("  ".join(f"{str(r[c] or ''):>14}" for c in cols))

print()
print("=" * 80)
print("4) signal_decisions — bugün onaylanan (k2 != REJECT)")
print("=" * 80)
try:
    rows2 = q("""
    SELECT source, symbol, k2_label, k3_action, created_at
    FROM signal_decisions
    WHERE date(created_at)='2026-06-04' AND k2_label != 'REJECT'
    """)
except Exception as e:
    print(f"(sorgu hatası — source/symbol kolonu yok: {e})")
    print()
    print("Alternatif (merter_symbol):")
    rows2 = q("""
    SELECT scenario_label, merter_symbol, k2_label, k3_action, created_at
    FROM signal_decisions
    WHERE date(created_at)='2026-06-04' AND k2_label != 'REJECT'
    """)
    cols = ["scenario_label", "merter_symbol", "k2_label", "k3_action", "created_at"]
    if not rows2:
        print("(kayıt yok)")
    else:
        print("  ".join(f"{c:>16}" for c in cols))
        for r in rows2:
            print("  ".join(f"{str(r[c] or ''):>16}" for c in cols))
    rows2 = None
if rows2 is not None:
    if not rows2:
        print("(kayıt yok)")
    else:
        cols = ["source", "symbol", "k2_label", "k3_action", "created_at"]
        print("  ".join(f"{c:>14}" for c in cols))
        for r in rows2:
            print("  ".join(f"{str(r[c] or ''):>14}" for c in cols))
'''

SHELL = f"""
echo '================================================================================'
echo '1) mina_bot.log — 2026-06-04 — TP / trailing / defense'
echo '================================================================================'
grep '2026-06-04' {REMOTE}/mina_bot.log 2>/dev/null | grep -iE 'tp|trailing|defense' || echo '(eşleşme yok)'

echo ''
echo '================================================================================'
echo '3) Merter DCA log — son 20 satır'
echo '================================================================================'
tail -20 {REMOTE}/signal_bot/merter_dca.log 2>&1 || echo '(dosya yok)'

echo ''
{REMOTE}/venv/bin/python {REMOTE_PY}
"""


def main():
    last_err = None
    for attempt in range(1, 4):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, username=USER, password=PASS, timeout=25)
            sftp = c.open_sftp()
            try:
                sftp.stat(REMOTE + "/scripts")
            except FileNotFoundError:
                sftp.mkdir(REMOTE + "/scripts")
            with sftp.open(REMOTE_PY, "w") as f:
                f.write(LOCAL_QUERY)
            sftp.close()
            _, stdout, stderr = c.exec_command(SHELL, timeout=120)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            print(out)
            if err.strip():
                print("STDERR:", err)
            c.close()
            return
        except OSError as e:
            last_err = e
            print(f"deneme {attempt}: {e}")
            import time
            time.sleep(2)
    print(f"SSH bağlanılamadı: {last_err}")
    sys.exit(1)


if __name__ == "__main__":
    main()
