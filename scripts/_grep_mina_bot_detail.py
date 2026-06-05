#!/usr/bin/env python3
import os, sys, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40', username='root', password=os.environ.get('MINA_SSH_PASS','REDACTED'), timeout=25)

queries = [
    ("BUGUN 4 SEMBOL", r"grep -E 'XRPUSDT|AVAXUSDT|BCHUSDT|BNBUSDT' /root/MINA_v2/mina_bot.log | grep '2026-06-03'"),
    ("BCH/BNB DEFANS DETAY", r"grep -E 'BCHUSDT|BNBUSDT' /root/MINA_v2/mina_bot.log | grep -iE 'defense|D1|D2|D3|ekle|LONG|market|fiyat|price|qty|margin' | grep '2026-06-03'"),
    ("XRP/AVAX TP TRAIL DETAY", r"grep -E 'XRPUSDT|AVAXUSDT' /root/MINA_v2/mina_bot.log | grep -iE 'TP|trailing|take_profit|max_prices|entry|open' | grep '2026-06-03'"),
    ("JOURNALCTL ENGINE BUGUN", r"journalctl -u mina-engine.service --since '2026-06-03 00:00:00' --no-pager 2>/dev/null | grep -E 'XRPUSDT|AVAXUSDT|BCHUSDT|BNBUSDT' | grep -iE 'D1|D2|defense|TP|trailing|ekle|fiyat' || true"),
]

for title, cmd in queries:
    print('=' * 90)
    print(title)
    print('=' * 90)
    _, out, err = c.exec_command(cmd, timeout=120)
    data = out.read().decode('utf-8', errors='replace')
    print(data if data.strip() else '(kayit yok)')
    e = err.read().decode('utf-8', errors='replace')
    if e.strip():
        print('stderr:', e)
    print()

c.close()
