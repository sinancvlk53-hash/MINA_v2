#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import paramiko
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

R = "/root/MINA_v2"

SECTIONS = [
    (
        "DERR trades (ADA*)",
        f"""{R}/venv/bin/python - <<'PY'
import sqlite3, json
conn = sqlite3.connect("{R}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id,symbol,side,leverage,status,open_time,close_time,close_reason,signal_source,open_price,open_qty,initial_margin "
    "FROM trades WHERE symbol LIKE '%ADA%' ORDER BY id DESC LIMIT 10"
).fetchall()
for r in rows:
    print(dict(r))
if not rows:
    print("(kayit yok)")
conn.close()
PY""",
    ),
    (
        "position_sources.json (ADA)",
        f"grep -i ada {R}/position_sources.json 2>/dev/null || echo '(eslesme yok)'",
    ),
    (
        "initial_entry_prices / margins / pending",
        f"grep -i ada {R}/initial_entry_prices.json {R}/initial_margins.json {R}/pending_orders.json 2>/dev/null || echo '(yok)'",
    ),
    (
        "merter_dca_state.json (ADA)",
        f"grep -i ada {R}/signal_bot/merter_dca_state.json 2>/dev/null || echo '(yok)'",
    ),
    (
        "merter_dca.log (ADA tail)",
        f"grep -i ADA {R}/signal_bot/merter_dca.log 2>/dev/null | tail -20 || echo '(yok)'",
    ),
    (
        "signals_log.txt (ADA tail)",
        f"grep -i ADA {R}/signal_bot/signals_log.txt 2>/dev/null | tail -30 || echo '(yok)'",
    ),
    (
        "mina_bot.log (ADA tail)",
        f"grep -i ADA {R}/mina_bot.log 2>/dev/null | tail -30 || echo '(yok)'",
    ),
    (
        "raw_signal_queue (ADA)",
        f"grep -i ada {R}/signal_bot/raw_signal_queue.json 2>/dev/null | tail -20 || echo '(yok)'",
    ),
    (
        "Binance ADA pozisyon detay",
        f"""{R}/venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, "{R}")
sys.path.insert(0, "{R}/backend")
os.chdir("{R}")
from dotenv import load_dotenv
load_dotenv("{R}/.env")
from config import BinanceConfig
for p in BinanceConfig().get_client().futures_position_information():
    if p.get("symbol") == "ADAUSDT" and float(p.get("positionAmt") or 0) != 0:
        print(p)
PY""",
    ),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=30)
    for title, cmd in SECTIONS:
        print("=" * 70)
        print(title)
        print("-" * 70)
        _, o, e = c.exec_command(cmd, timeout=60)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        print(out if out.strip() else "(bos)")
        if err.strip():
            print("ERR:", err)
    c.close()


if __name__ == "__main__":
    main()
