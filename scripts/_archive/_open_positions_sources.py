#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import json
import paramiko
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

R = "/root/MINA_v2"
SYMS = ("SOLUSDT", "MOODENGUSDT", "ADAUSDT", "LINKUSDT")

REMOTE = f"""{R}/venv/bin/python - <<'PY'
import sqlite3, json, os, sys
sys.path.insert(0, "{R}")
R = "{R}"
syms = {list(SYMS)!r}

conn = sqlite3.connect(f"{{R}}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row

print("=== DERR open trades (4 sembol) ===")
for sym in syms:
    rows = conn.execute(
        "SELECT id,symbol,side,leverage,status,signal_source,open_time,open_price,open_qty,initial_margin,defense_triggered "
        "FROM trades WHERE symbol=? AND status='open' ORDER BY id DESC LIMIT 1",
        (sym,),
    ).fetchall()
    print(f"--- {{sym}} ---")
    if rows:
        print(dict(rows[0]))
    else:
        print("(açık kayıt yok)")

print()
print("=== position_sources.json ===")
ps = json.load(open(f"{{R}}/position_sources.json"))
for sym in syms:
    key = f"{{sym}}_LONG"
    print(f"{{key}}: {{ps.get(key, '(yok)')}}")

print()
print("=== merter_dca_state (varsa) ===")
try:
    st = json.load(open(f"{{R}}/signal_bot/merter_dca_state.json"))
    for yuva, pos in (st.get("positions") or {{}}).items():
        if (pos.get("symbol") or "").upper() in syms:
            print(yuva, pos)
except Exception as e:
    print(e)

print()
print("=== Binance açık (leverage) ===")
sys.path.insert(0, f"{{R}}/backend")
os.chdir(R)
from dotenv import load_dotenv
load_dotenv(f"{{R}}/.env")
from config import BinanceConfig
for p in BinanceConfig().get_client().futures_position_information():
    if p.get("symbol") in syms and float(p.get("positionAmt") or 0) != 0:
        print(p["symbol"], "lev="+str(p.get("leverage")), "amt="+str(p.get("positionAmt")))
conn.close()
PY"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
    _, o, e = c.exec_command(REMOTE, timeout=90)
    print(o.read().decode("utf-8", errors="replace"), end="")
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
    c.close()


if __name__ == "__main__":
    main()
