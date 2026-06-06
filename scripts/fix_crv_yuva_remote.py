#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRV trade_id=50 yuva onarımı — deploy sonrası sunucuda reconcile çalıştır."""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE_SCRIPT = r'''
cd /root/MINA_v2
/root/MINA_v2/venv/bin/python - <<'PY'
import json, sqlite3, sys
sys.path.insert(0, "/root/MINA_v2")
from signal_bot.merter_dca_manager import get_merter_dca_manager

print("=== DERR trade_id=50 (once) ===")
conn = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT id,symbol,signal_source,status FROM trades WHERE id=50").fetchone()
print(dict(r) if r else "(yok)")
conn.close()

mgr = get_merter_dca_manager()
print("\n=== reconcile ===")
n = mgr.reconcile_state_from_derr()
print(f"updates={n}")

print("\n=== DERR trade_id=50 (sonra) ===")
conn = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT id,symbol,signal_source,status FROM trades WHERE id=50").fetchone()
print(dict(r) if r else "(yok)")
conn.close()

print("\n=== merter_dca_state.json ===")
print(json.dumps(mgr.state, indent=2, ensure_ascii=False))

print("\n=== son log ===")
import subprocess
subprocess.run(["tail", "-5", "/root/MINA_v2/signal_bot/merter_dca.log"])
PY
systemctl restart mina-merter-dca.service
sleep 2
systemctl is-active mina-merter-dca.service
'''


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_SCRIPT, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        path = os.path.join(_ROOT, "crv_yuva_fix_out.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
            if err.strip():
                f.write("\nSTDERR:\n" + err)
        print(f"written: {path}")
        print(out[-2000:] if len(out) > 2000 else out)
    finally:
        client.close()


if __name__ == "__main__":
    main()
