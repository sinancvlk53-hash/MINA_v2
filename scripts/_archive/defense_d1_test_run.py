#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Savunma D1 testi — kullanıcı adımları."""
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
OUT = os.path.join(_ROOT, "defense_test_run_out.txt")
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

    lines.append("========== ADIM 1 ==========")
    for f in ("initial_entry_prices.json", "defense_levels.json", "position_states.json"):
        run(client, f"cat {REMOTE}/{f}")

    init_raw = run(client, f"cat {REMOTE}/initial_entry_prices.json")
    init_data = json.loads(init_raw)
    defense_raw = run(client, f"cat {REMOTE}/defense_levels.json")
    defense_data = json.loads(defense_raw)

    # SOL veya LINK — defense=0 olanı tercih et
    key = None
    for candidate in ("LINKUSDT_LONG", "SOLUSDT_LONG"):
        if candidate in init_data and int(defense_data.get(candidate, 0)) == 0:
            key = candidate
            break
    if key is None:
        key = "LINKUSDT_LONG" if "LINKUSDT_LONG" in init_data else "SOLUSDT_LONG"

    old_entry = float(init_data[key])
    new_entry = round(old_entry * 1.06, 8)
    init_data[key] = new_entry

    lines.append(f"\n========== ADIM 2-3: {key} {old_entry} -> {new_entry} (x1.06) ==========")
    run(client, f"cp {REMOTE}/initial_entry_prices.json {REMOTE}/initial_entry_prices.json.bak_defense_test")
    payload = json.dumps(init_data, indent=2, ensure_ascii=False)
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE}/initial_entry_prices.json", "w") as f:
        f.write(payload)
    sftp.close()
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    lines.append("\n========== ADIM 4: tail -f 120s ==========")
    sym = key.replace("_LONG", "")
    run(
        client,
        f"timeout 120 tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'{sym}|defense|D1|defense_level' || true",
        timeout=130,
    )

    lines.append("\n========== ADIM 5 ==========")
    run(client, f"grep {sym} {REMOTE}/mina_bot.log | tail -10")
    run(client, f"cat {REMOTE}/defense_levels.json")
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); "
        "c.row_factory=sqlite3.Row; "
        f"rows=c.execute(\\\"SELECT id,symbol,side,defense_triggered,defense_prices,weighted_avg_price,open_qty,status "
        f"FROM trades WHERE symbol='{sym}' AND status='open'\\\").fetchall(); "
        "[print(dict(r)) for r in rows]\""
    ))
    run(client, f"cat {REMOTE}/initial_margins.json | python3 -c \"import sys,json; d=json.load(sys.stdin); print(json.dumps({{k:v for k,v in d.items() if '{sym[:4]}' in k}}, indent=2))\"")

    lines.append("\n========== ADIM 6: GERİ YÜKLEME ==========")
    run(client, f"mv {REMOTE}/initial_entry_prices.json.bak_defense_test {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
