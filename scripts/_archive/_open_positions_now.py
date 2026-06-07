#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import paramiko
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

REMOTE = """/root/MINA_v2/venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, "/root/MINA_v2")
sys.path.insert(0, "/root/MINA_v2/backend")
os.chdir("/root/MINA_v2")
from dotenv import load_dotenv
load_dotenv("/root/MINA_v2/.env")
from config import BinanceConfig
client = BinanceConfig().get_client()
raw = client.futures_position_information()
rows = []
for p in raw:
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    pnl = float(p.get("unRealizedProfit") or 0)
    iso = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
    lev = int(p.get("leverage") or 4)
    if iso <= 0 and entry > 0:
        iso = abs(amt) * entry / max(lev, 1)
    roe = (pnl / iso * 100) if iso > 0 else 0.0
    rows.append((p["symbol"], side, entry, mark, pnl, roe))
print(f"OPEN_COUNT={len(rows)}")
print("symbol\\tside\\tentry\\tmark\\tpnl_usdt\\troe_pct")
for r in rows:
    print(f"{r[0]}\\t{r[1]}\\t{r[2]:.8f}\\t{r[3]:.8f}\\t{r[4]:+.4f}\\t{r[5]:+.2f}")
PY"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
    _, o, e = c.exec_command(REMOTE, timeout=60)
    print(o.read().decode("utf-8", errors="replace"), end="")
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, end="")
    c.close()


if __name__ == "__main__":
    main()
