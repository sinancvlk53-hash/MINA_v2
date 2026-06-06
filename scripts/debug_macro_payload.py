#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Sunucudan macro_levels.json + WS macroLevels payload örneği."""
import json
import os
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)

# macro_levels.json
_, o, _ = c.exec_command(f"cat {REMOTE}/signal_bot/macro_levels.json", timeout=15)
macro_raw = o.read().decode("utf-8", errors="replace")
print("=== macro_levels.json (sunucu) ===")
print(macro_raw[:4000])
if len(macro_raw) > 4000:
    print(f"... ({len(macro_raw)} chars total)")

# get_macro_levels() output
py = f"""
import json, os, sys
os.environ['MINA_DATA_ROOT'] = '{REMOTE}'
sys.path.insert(0, '{REMOTE}')
from dashboard.dashboard_ws import get_macro_levels
lv = get_macro_levels()
filled = [x for x in lv if (x.get('snippet') or '').strip()]
print('=== get_macro_levels() ===')
print('total', len(lv), 'filled', len(filled))
print(json.dumps(lv, ensure_ascii=False, indent=2))
"""
_, o, e = c.exec_command(
    f"cd {REMOTE} && {REMOTE}/venv/bin/python -c {json.dumps(py)}",
    timeout=30,
)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
print(out)
if err.strip():
    print("STDERR:", err[:500])

c.close()
