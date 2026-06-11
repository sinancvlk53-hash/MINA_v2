#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMDS = [
("1. ZEC kayıtları", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
rows = conn.execute('''
    SELECT id, symbol, direction, entry_price, tp_price, 
           stop_price, baz_fiyat, fiyat_4s, result
    FROM ht_pdf_basari_orani 
    WHERE symbol LIKE '%ZEC%'
    ORDER BY created_at DESC
''').fetchall()
for r in rows: print(r)
conn.close()
" """),
("2. check_pending_signals", r"""cd /root/MINA_v2 && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()
import sys
sys.path.insert(0, '/root/MINA_v2')
from signal_bot.ht_pdf_price_monitor import check_pending_signals
n = check_pending_signals()
print('Tamamlandı, sonuçlanan:', n)
" """),
("3. XAG iptal", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
conn.execute(\"UPDATE ht_pdf_basari_orani SET status='cancelled', result='conflict' WHERE id IN (37, 46)\")
conn.commit()
print('XAG çelişki kayıtları iptal edildi')
conn.close()
" """),
("ZEC sonrası", r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
rows = conn.execute('''
    SELECT id, direction, tp_price, fiyat_4s, result, status
    FROM ht_pdf_basari_orani WHERE symbol LIKE '%ZEC%' ORDER BY id
''').fetchall()
for r in rows: print(r)
conn.close()
" """),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
for title, cmd in CMDS:
    print("=" * 60, title, "=" * 60, sep="\n")
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("ERR:", err)
c.close()
