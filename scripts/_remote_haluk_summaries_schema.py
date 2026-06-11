#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && python3 -c "import sqlite3; conn = sqlite3.connect('mina_trading_journal.db'); cols = conn.execute('PRAGMA table_info(haluk_yayin_summaries)').fetchall(); [print(c) for c in cols]; conn.close()" """

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=60)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
if err.strip():
    sys.stdout.buffer.write(b"\nERR: " + err.encode("utf-8", errors="replace"))
c.close()
