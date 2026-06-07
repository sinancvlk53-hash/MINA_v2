#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Görev 3: en son PDF parse + macro_levels TOTAL SR kontrolü."""
import json
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
R = "/root/MINA_v2"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)

print("=== ls -lt pdfs (head -5) ===")
_, o, _ = c.exec_command(f"ls -lt {R}/signal_bot/pdfs/ | head -5", timeout=15)
ls_out = o.read().decode("utf-8", errors="replace")
print(ls_out)

# En son PDF yolu
_, o2, _ = c.exec_command(
    f"ls -t {R}/signal_bot/pdfs/*.pdf 2>/dev/null | head -1",
    timeout=15,
)
pdf = o2.read().decode("utf-8", errors="replace").strip()
if not pdf:
    print("PDF bulunamadi")
    c.close()
    raise SystemExit(1)

rel = pdf.replace(f"{R}/", "")
print(f"\n=== Parser: {rel} ===")
cmd = f"cd {R} && PYTHONPATH={R} {R}/venv/bin/python signal_bot/haluk_pdf_parser.py {rel} 2>&1"
_, o3, _ = c.exec_command(cmd, timeout=600)
parser_out = o3.read().decode("utf-8", errors="replace")
print(parser_out[-12000:] if len(parser_out) > 12000 else parser_out)

print("\n=== Claude Vision log satirlari ===")
vision_lines = [
    ln for ln in parser_out.splitlines()
    if "HALUK VISUAL" in ln or "Görsel makro" in ln or "Gorsel makro" in ln
]
if vision_lines:
    for ln in vision_lines:
        print(ln)
else:
    print("(HALUK VISUAL log yok)")

print("\n=== macro_levels.json ===")
_, o4, _ = c.exec_command(f"cat {R}/signal_bot/macro_levels.json", timeout=15)
macro_raw = o4.read().decode("utf-8", errors="replace")
print(macro_raw)

data = json.loads(macro_raw)
total = next(x for x in data["levels"] if x["coin"] == "TOTAL")
others = next(x for x in data["levels"] if x["coin"] == "OTHERS")

print("\n=== TOTAL ===")
print("supports:", total.get("supports"))
print("resistances:", total.get("resistances"))
print("snippet:", (total.get("snippet") or "")[:100])
print("SR dolu:", bool(total.get("supports") or total.get("resistances")))

print("\n=== OTHERS (birikim testi — bu PDF'de yoksa eski kalmalı) ===")
print("snippet:", (others.get("snippet") or "")[:80])
print("source:", others.get("source"))
print("updated_at:", others.get("updated_at"))

c.close()
