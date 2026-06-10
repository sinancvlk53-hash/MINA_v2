#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
cd /root/MINA_v2
export PYTHONPATH=/root/MINA_v2

echo "========== 1. Anthropic API test =========="
/root/MINA_v2/venv/bin/python3 << 'PY1'
from dotenv import load_dotenv
load_dotenv()
import os
import anthropic
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
msg = client.messages.create(
    model='claude-sonnet-4-6',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'test'}]
)
print('API OK:', msg.content)
PY1

echo ""
echo "========== 2. Son PDF parse =========="
/root/MINA_v2/venv/bin/python3 << 'PY2'
from dotenv import load_dotenv
load_dotenv()
import sys
import glob
sys.path.insert(0, '/root/MINA_v2')
from signal_bot.haluk_pdf_visual import extract_trading_signals
pdfs = sorted(glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'))
if not pdfs:
    print('PDF bulunamadi')
else:
    last_pdf = pdfs[-1]
    print(f'PDF: {last_pdf}')
    signals = extract_trading_signals(last_pdf)
    print(f'Sinyal sayisi: {len(signals)}')
    for s in signals:
        print(s)
PY2
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c, timeout=30)
    _, stdout, stderr = c.exec_command(REMOTE, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stderr.buffer.write(("STDERR:\n" + err).encode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
