#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
echo "=== pdf listener / signals log ==="
grep -i "pdf\|haluk\|parse\|visual" /root/MINA_v2/signal_bot/signals_log.txt 2>/dev/null | tail -20 || echo "(yok)"
journalctl -u mina-pdf-listener -n 15 --no-pager 2>/dev/null | tail -15

echo ""
echo "=== Son PDF: haluk_pdf_parser (approval_bot yolu) ==="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
import glob, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '/root/MINA_v2')
pdf = sorted(glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'))[-1]
print(f'PDF: {pdf}')
from signal_bot.signal_parser import parse_haluk_pdf_path
records, pause = parse_haluk_pdf_path(pdf)
print(f'pause={pause} kayit={len(records)}')
for r in records[:15]:
    print(r)
if len(records) > 15:
    print(f'... +{len(records)-15} daha')
PY

echo ""
echo "=== Son PDF: visual extract (dotenv ile) ==="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY2'
import glob, os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '/root/MINA_v2')
pdf = sorted(glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'))[-1]
print(f'PDF: {pdf}')
print(f'ANTHROPIC set: {bool(os.getenv("ANTHROPIC_API_KEY"))}')
from signal_bot.haluk_pdf_visual import extract_trading_signals
signals = extract_trading_signals(pdf)
print(f'Sinyal sayisi: {len(signals)}')
for s in signals[:10]:
    print(s)
PY2
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, stderr = c.exec_command(REMOTE, timeout=300)
sys.stdout.buffer.write(stdout.read())
err = stderr.read().decode('utf-8', errors='replace')
if err.strip():
    sys.stdout.buffer.write(b'\nSTDERR:\n')
    sys.stdout.buffer.write(err.encode('utf-8', errors='replace'))
c.close()
