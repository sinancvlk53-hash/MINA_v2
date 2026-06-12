#!/usr/bin/env python3
"""MINA v2 tam sistem raporu — sunucu veri toplama."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import paramiko
from mina_ssh import connect_paramiko

OUT = os.path.join(_ROOT, "scripts", "_sistem_raporu_output.txt")

SECTIONS = [
    ("1. Aktif mina servisleri", "systemctl list-units --type=service --state=active --no-pager 2>/dev/null | grep mina || echo '(yok)'"),
    ("2. Python dosyaları (ls -la)", r"find /root/MINA_v2 -name '*.py' | grep -v venv | grep -v __pycache__ | xargs ls -la 2>/dev/null | sort -k6,7 | tail -80"),
    ("3. Dashboard src dosyaları", r"find /root/MINA_v2/dashboard/src -name '*.jsx' -o -name '*.js' 2>/dev/null | grep -v node_modules | sort"),
    ("4. DB tablo şemaları", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
tables = [t[0] for t in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]
for table in sorted(tables):
    print(f'\n=== {table} ===')
    cols = conn.execute(f'PRAGMA table_info({table})').fetchall()
    for c in cols: print(f'  {c[1]} ({c[2]})')
conn.close()
" """),
    ("5. Git log -20", "cd /root/MINA_v2 && git log --oneline -20 2>/dev/null"),
    ("6. systemd mina units", "ls -la /etc/systemd/system/mina-*.service 2>/dev/null"),
    ("7. .env değişken isimleri", r"grep -E '^[A-Z_]+=.' /root/MINA_v2/.env 2>/dev/null | sed 's/=.*/=***/' || echo '(yok)'"),
    ("9. DERR son 24 saat", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
from datetime import datetime, timedelta
conn = sqlite3.connect('mina_trading_journal.db')
since = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
try:
    rows = conn.execute('''
        SELECT symbol, side, leverage, open_price, status, 
               pnl_usdt, close_reason, signal_source, open_time
        FROM trades WHERE open_time > ? ORDER BY open_time DESC
    ''', (since,)).fetchall()
    print(f'Son 24 saat: {len(rows)} işlem')
    for r in rows: print(r)
except Exception as e:
    print('HATA:', e)
conn.close()
" """),
    ("Binance pozisyon özeti", r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv; load_dotenv()
import os, sys; sys.path.insert(0,'/root/MINA_v2')
from binance.client import Client
c=Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
pos=[p for p in c.futures_position_information() if float(p['positionAmt'])!=0]
ords=c.futures_get_open_orders()
print(f'Açık pozisyon: {len(pos)}, bekleyen emir: {len(ords)}')
for p in pos: print(p['symbol'], p['positionSide'], p['positionAmt'], p['entryPrice'])
" """),
    ("Servis status özeti", "systemctl is-active mina-engine mina-listener mina-ht-listener mina-approval-bot mina-dashboard-ws mina-dashboard-vite mina-haluk-yayin 2>&1"),
]

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c)
    lines = []
    for title, cmd in SECTIONS:
        lines.append("=" * 70)
        lines.append(title)
        lines.append("=" * 70)
        _, o, e = c.exec_command(cmd, timeout=180)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        lines.append(out)
        if err.strip():
            lines.append("STDERR: " + err)
        lines.append("")
    c.close()
    body = "\n".join(lines)
    sys.stdout.buffer.write(body.encode("utf-8", errors="replace"))

if __name__ == "__main__":
    main()
