#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, paramiko
PASS = require_ssh_pass()
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40",username="root",password=PASS,timeout=30)
cmd="""
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python -c "
import fitz
from signal_bot.haluk_pdf_visual import render_pdf_pages_png, VISUAL_MACRO_SYMBOLS
import glob
pdfs=sorted(glob.glob('signal_bot/pdfs/*.pdf'))
print('pymupdf', fitz.__doc__[:20] if fitz.__doc__ else 'ok')
print('symbols', VISUAL_MACRO_SYMBOLS)
if pdfs:
    p=pdfs[-1]
    pages=render_pdf_pages_png(p)
    print('pdf', p, 'pages', len(pages), 'first_png_bytes', len(pages[0][1]) if pages else 0)
else:
    print('no pdf')
"
"""
_,o,e=c.exec_command(cmd,timeout=30)
print(o.read().decode("utf-8",errors="replace"))
print(e.read().decode("utf-8",errors="replace"))
c.close()
