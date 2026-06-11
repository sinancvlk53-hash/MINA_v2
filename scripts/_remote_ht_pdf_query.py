#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('mina_trading_journal.db')
cols = [d[1] for d in conn.execute('PRAGMA table_info(ht_pdf_basari_orani)').fetchall()]
rows = conn.execute('''
    SELECT * FROM ht_pdf_basari_orani 
    ORDER BY created_at DESC 
    LIMIT 20
''').fetchall()
print('KOLONLAR:', cols)
print(f'Toplam kayıt: {len(rows)}')
print()
for r in rows:
    for c,v in zip(cols,r): print(f'{c}: {v}')
    print('---')
conn.close()
" """

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=90)
sys.stdout.buffer.write(o.read())
err = e.read().decode()
if err.strip():
    print("ERR:", err)
c.close()
