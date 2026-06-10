#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && source venv/bin/activate && python3 << 'PYEOF'
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, '/root/MINA_v2')
from signal_bot.haluk_pdf_visual import extract_trading_signals
signals = extract_trading_signals('/root/MINA_v2/signal_bot/pdfs/tg_20260610_135400_11669.pdf')
print(f'Toplam sinyal: {len(signals)}')
for s in signals:
    print(s)
PYEOF"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=300)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
report = (out or "") + ("\nERR:\n" + err if err.strip() else "")
out_path = os.path.join(_ROOT, "scripts", "_pdf_extract_result.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(report)
sys.stdout.buffer.write(report.encode("utf-8", errors="replace"))
c.close()
