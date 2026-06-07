#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINK D3 savunma testi."""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"
OUT = os.path.join(_ROOT, "defense_d3_link_out.txt")
lines: list[str] = []


def run(client, cmd: str, timeout: int = 130) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    lines.append(f"$ {cmd}\n{out}")
    if err.strip():
        lines.append(f"STDERR:\n{err}")
    return out


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)

    lines.append("========== ÖNCE ==========")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/defense_levels.json")

    mark_raw = run(
        client,
        f"{REMOTE}/venv/bin/python -c \"import requests; "
        "print(requests.get('https://fapi.binance.com/fapi/v1/ticker/price',"
        "params={'symbol':'LINKUSDT'},timeout=10).json()['price'])\"",
    ).strip().split("\n")[-1]
    mark = float(mark_raw)

    init_raw = run(client, f"cat {REMOTE}/initial_entry_prices.json")
    init_data = json.loads(init_raw)
    key = "LINKUSDT_LONG"
    old_entry = float(init_data[key])
    new_entry = round(mark / 0.74, 8)

    lines.append(f"\n========== D3 TEST: mark={mark} old={old_entry} new={new_entry} (mark/0.74) ==========")
    run(client, f"cp {REMOTE}/initial_entry_prices.json {REMOTE}/initial_entry_prices.json.bak_d3_test")
    init_data[key] = new_entry
    payload = json.dumps(init_data, indent=2, ensure_ascii=False)
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE}/initial_entry_prices.json", "w") as f:
        f.write(payload)
    sftp.close()
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    lines.append("\n========== tail -f 120s ==========")
    run(
        client,
        f"timeout 120 tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'LINKUSDT|defense|D3|SFP|sfp|bull|4H|ekleme|HARD' || true",
        timeout=130,
    )

    lines.append("\n========== SONUÇ ==========")
    run(client, f"grep -E 'LINKUSDT.*defense|D3|SFP|sfp|HARD' {REMOTE}/mina_bot.log | tail -20")
    run(client, f"grep -iE 'D3|SFP|LINKUSDT' {REMOTE}/mina_bot.log | tail -25")
    run(client, f"cat {REMOTE}/defense_levels.json")
    run(client, f"cat {REMOTE}/mina_position_state.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('LINKUSDT',d.get('LINKUSDT_LONG','yok')), indent=2))\"")
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); "
        "c.row_factory=sqlite3.Row; "
        "rows=c.execute(\\\"SELECT id,symbol,defense_triggered,defense_prices,weighted_avg_price,open_qty,status "
        "FROM trades WHERE symbol='LINKUSDT' AND status='open'\\\").fetchall(); "
        "[print(dict(r)) for r in rows]\""
    ))

    lines.append("\n========== GERİ YÜKLEME ==========")
    run(client, f"mv {REMOTE}/initial_entry_prices.json.bak_d3_test {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
