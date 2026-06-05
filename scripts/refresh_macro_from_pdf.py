#!/usr/bin/env python3
import glob
import json
import os
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from signal_bot.haluk_pdf_parser import parse_haluk_pdf
from signal_bot.macro_levels_store import load_macro_levels

pdfs = glob.glob(os.path.join(ROOT, "signal_bot/pdfs/*.pdf"))
if pdfs:
    p = max(pdfs, key=os.path.getmtime)
    print("Re-parse:", p)
    parse_haluk_pdf(p)
else:
    print("PDF yok")

data = load_macro_levels()
print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
