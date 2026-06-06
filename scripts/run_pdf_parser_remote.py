#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os
import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
PDF = "signal_bot/pdfs/tg_20260606_054706_11519.pdf"
REMOTE = "/root/MINA_v2"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)

print("=== haluk_pdf_parser.py ===")
cmd = f"cd {REMOTE} && {REMOTE}/venv/bin/python signal_bot/haluk_pdf_parser.py {PDF}"
_, o, e = c.exec_command(cmd, timeout=600)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
print(out)
if err.strip():
    print("--- stderr ---")
    print(err)

print("\n=== macro_levels.json ===")
_, o2, _ = c.exec_command(f"cat {REMOTE}/signal_bot/macro_levels.json", timeout=30)
macro = o2.read().decode("utf-8", errors="replace")
print(macro)

# TOTAL özeti
import json
try:
    data = json.loads(macro)
    total = next((x for x in data.get("levels", []) if x.get("coin") == "TOTAL"), None)
    print("\n=== TOTAL özeti ===")
    if total:
        print(f"supports: {total.get('supports')}")
        print(f"resistances: {total.get('resistances')}")
        print(f"snippet: {(total.get('snippet') or '')[:80]}...")
        filled = bool(total.get("supports")) or bool(total.get("resistances"))
        print(f"SR dolu: {'EVET' if filled else 'HAYIR'}")
    else:
        print("TOTAL kaydı bulunamadı")
except Exception as ex:
    print("JSON parse:", ex)

c.close()
