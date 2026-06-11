#!/usr/bin/env python3
"""PDF sistem röntgeni — sunucu audit."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import paramiko
from mina_ssh import connect_paramiko

SECTIONS = [
    ("1. haluk_pdf_visual.py", "cat /root/MINA_v2/signal_bot/haluk_pdf_visual.py"),
    ("2. haluk_pdf_parser.py", "cat /root/MINA_v2/signal_bot/haluk_pdf_parser.py"),
    ("3. approval_bot.py (head 100)", "head -100 /root/MINA_v2/signal_bot/approval_bot.py"),
    ("4. mina_ht_pdf_supersede.py", "cat /root/MINA_v2/mina_ht_pdf_supersede.py"),
    ("5. mina_entry_orders haluk_pdf grep", r"grep -A 30 'haluk_pdf\|is_haluk' /root/MINA_v2/mina_entry_orders.py || echo '(eşleşme yok)'"),
    ("6. ht_signals_queue.json", "cat /root/MINA_v2/signal_bot/ht_signals_queue.json 2>/dev/null | python3 -m json.tool || echo '(dosya yok veya boş)'"),
    ("7. ht_pdf_basari_orani son 10", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
try:
    cols = [d[1] for d in conn.execute('PRAGMA table_info(ht_pdf_basari_orani)').fetchall()]
    rows = conn.execute('SELECT * FROM ht_pdf_basari_orani ORDER BY created_at DESC LIMIT 10').fetchall()
    print('KOLONLAR:', cols)
    for r in rows:
        for c,v in zip(cols,r): print(f'{c}: {v}')
        print('---')
except Exception as e:
    print('HATA:', e)
conn.close()
" """),
    ("8. Binance pozisyon + emirler", r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'), testnet=True)
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
orders = client.futures_get_open_orders()
print(f'Açık pozisyon: {len(positions)}')
for p in positions: print(p['symbol'], p['positionAmt'], p['entryPrice'])
print(f'Bekleyen emir: {len(orders)}')
for o in orders: print(o['symbol'], o['side'], o['price'], o['type'])
" """),
    ("9a. mina_bot.log pdf tail", r"grep -i 'pdf\|visual\|signal\|sinyal\|error\|hata' /root/MINA_v2/mina_bot.log 2>/dev/null | tail -50 || echo '(log yok veya eşleşme yok)'"),
    ("9b. journalctl mina-pdf-listener", "journalctl -u mina-pdf-listener -n 30 --no-pager 2>/dev/null || echo '(servis yok)'"),
    ("9c. journalctl mina-approval-bot", "journalctl -u mina-approval-bot -n 30 --no-pager 2>/dev/null || echo '(servis yok)'"),
    ("9d. journalctl mina-ht-listener", "journalctl -u mina-ht-listener -n 30 --no-pager 2>/dev/null || echo '(servis yok)'"),
]

OUT = os.path.join(_ROOT, "scripts", "_pdf_rontgen_output.txt")

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c)
    lines = []
    for title, cmd in SECTIONS:
        lines.append("=" * 80)
        lines.append(title)
        lines.append("=" * 80)
        _, o, e = c.exec_command(cmd, timeout=120)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        lines.append(out)
        if err.strip():
            lines.append("STDERR: " + err)
        lines.append("")
    c.close()
    body = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    print(body)
    print(f"\n>>> Kaydedildi: {OUT}")

if __name__ == "__main__":
    main()
