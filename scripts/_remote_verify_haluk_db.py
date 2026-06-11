#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && python3 -c "
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
print('=== haluk_yayin_summaries ===')
for c in conn.execute('PRAGMA table_info(haluk_yayin_summaries)').fetchall():
    print(c)
print('=== haluk_coin_analizleri ===')
for c in conn.execute('PRAGMA table_info(haluk_coin_analizleri)').fetchall():
    print(c)
conn.close()
" """

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=60)
print(o.read().decode())
err = e.read().decode()
if err.strip():
    print("ERR:", err)
c.close()
