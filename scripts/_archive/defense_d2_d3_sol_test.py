#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOL D2 + D3 savunma testi."""
from __future__ import annotations

import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"
OUT = os.path.join(_ROOT, "defense_d2_d3_sol_out.txt")
lines: list[str] = []


def run(client, cmd: str, timeout: int = 130) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    lines.append(f"$ {cmd}\n{out}")
    if err.strip():
        lines.append(f"STDERR:\n{err}")
    return out


def mark_price(client) -> float:
    raw = run(
        client,
        f"{REMOTE}/venv/bin/python -c \"import requests; "
        "print(requests.get('https://fapi.binance.com/fapi/v1/ticker/price',"
        "params={'symbol':'SOLUSDT'},timeout=10).json()['price'])\"",
    ).strip().split("\n")[-1]
    return float(raw)


def check_state(client, label: str) -> None:
    lines.append(f"\n--- {label} ---")
    run(client, f"cat {REMOTE}/defense_levels.json")
    run(client, (
        f"cat {REMOTE}/mina_position_state.json | python3 -c \""
        "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('SOLUSDT','yok'), indent=2))\""
    ))
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); "
        "c.row_factory=sqlite3.Row; "
        "rows=c.execute(\\\"SELECT id,symbol,defense_triggered,defense_prices,weighted_avg_price,open_qty,status "
        "FROM trades WHERE symbol='SOLUSDT' AND status='open'\\\").fetchall(); "
        "[print(dict(r)) for r in rows]\""
    ))


def set_entry(client, new_entry: float) -> None:
    init_raw = run(client, f"cat {REMOTE}/initial_entry_prices.json")
    init_data = json.loads(init_raw)
    init_data["SOLUSDT_LONG"] = round(new_entry, 8)
    payload = json.dumps(init_data, indent=2, ensure_ascii=False)
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE}/initial_entry_prices.json", "w") as f:
        f.write(payload)
    sftp.close()
    run(client, f"cat {REMOTE}/initial_entry_prices.json")


def tail_logs(client, seconds: int = 120) -> None:
    run(
        client,
        f"timeout {seconds} tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'SOLUSDT|defense|D2|D3|SFP|sfp|bull|4H|breakeven' || true",
        timeout=seconds + 15,
    )


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)

    lines.append("========== ADIM 0: BAŞLANGIÇ ==========")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/defense_levels.json")
    check_state(client, "baslangic")

    run(client, f"cp {REMOTE}/initial_entry_prices.json {REMOTE}/initial_entry_prices.json.bak_d2d3_test")

    lines.append("\n========== ADIM 1: MARK FİYAT ==========")
    mark1 = mark_price(client)
    lines.append(f"SOL mark = {mark1}")

    lines.append("\n========== ADIM 2: D2 TEST (mark/0.87) ==========")
    d2_entry = mark1 / 0.87
    lines.append(f"D2 entry = {d2_entry}")
    set_entry(client, d2_entry)
    check_state(client, "D2 oncesi dosyalar")
    lines.append("\n--- D2 tail 120s ---")
    tail_logs(client, 120)
    run(client, f"grep SOLUSDT {REMOTE}/mina_bot.log | tail -8")
    run(client, "journalctl -u mina-engine.service --since '3 min ago' --no-pager | grep -iE 'SOL|D2|SFP|defense' || true")
    check_state(client, "D2 sonrasi")

    lines.append("\n========== ADIM 3: D3 TEST (mark/0.74) ==========")
    mark2 = mark_price(client)
    lines.append(f"SOL mark (D3 icin) = {mark2}")
    d3_entry = mark2 / 0.74
    lines.append(f"D3 entry = {d3_entry}")
    set_entry(client, d3_entry)
    check_state(client, "D3 oncesi dosyalar")
    lines.append("\n--- D3 tail 120s ---")
    tail_logs(client, 120)
    run(client, f"grep -iE 'SOLUSDT.*defense|D3|SFP|sfp' {REMOTE}/mina_bot.log | tail -15")
    run(client, "journalctl -u mina-engine.service --since '3 min ago' --no-pager | grep -iE 'SOL|D3|SFP|defense|bull|4H' || true")
    check_state(client, "D3 sonrasi")

    lines.append("\n========== ADIM 6: GERİ YÜKLEME ==========")
    run(client, f"mv {REMOTE}/initial_entry_prices.json.bak_d2d3_test {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
