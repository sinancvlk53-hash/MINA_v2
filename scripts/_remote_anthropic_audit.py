#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
echo "========== 1. Claude API cagrilari =========="
grep -rn "anthropic\|claude\|messages.create\|client.messages" /root/MINA_v2/ --include="*.py" 2>/dev/null | grep -v "venv\|.pyc\|test" | grep -v "^Binary" | head -80

echo ""
echo "========== 2. model / max_tokens =========="
grep -rn "model=\|max_tokens=" /root/MINA_v2/ --include="*.py" 2>/dev/null | grep -v "venv\|.pyc" | head -40

echo ""
echo "========== 6. Son 24s tahmini =========="
echo "messages.create satirlari haluk_yayin_analiz.py:"
grep -c "messages.create" /root/MINA_v2/signal_bot/haluk_yayin_analiz.py 2>/dev/null || echo 0
echo ""
echo "Transcripts:"
ls -lt /root/MINA_v2/signal_bot/history/transcripts/ 2>/dev/null | head -5 || echo "YOK"
echo ""
wc -l /root/MINA_v2/signal_bot/haluk_tum.txt 2>/dev/null || echo "haluk_tum.txt YOK"
echo ""
echo "yayin_analiz.log son 20:"
tail -20 /root/MINA_v2/signal_bot/yayin_analiz.log 2>/dev/null || echo "(log yok)"
echo ""
echo "PDF sayfa sayisi son PDF:"
/root/MINA_v2/venv/bin/python3 << 'PY'
import glob
try:
    import fitz
    pdf = sorted(glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'))[-1]
    doc = fitz.open(pdf)
    print(f'{pdf}: {len(doc)} sayfa')
except Exception as e:
    print(e)
PY
echo ""
echo "Servisler (claude kullanan):"
systemctl is-active mina-haluk-yayin.service mina-ht-listener.service mina-pdf-listener.service 2>/dev/null
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=120)
sys.stdout.buffer.write(stdout.read())
c.close()
