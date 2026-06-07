#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINA savunma D1 testi — sunucu."""
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
OUT = os.path.join(_ROOT, "defense_test_out.txt")
lines: list[str] = []


def run(client, cmd: str, timeout: int = 60) -> str:
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
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)

    lines.append("========== 1) MEVCUT DURUM ==========")
    for f in ("initial_entry_prices.json", "defense_levels.json", "position_states.json"):
        run(client, f"cat {REMOTE}/{f}")

    # SOL seç — initial_entry oku
    init_raw = run(client, f"cat {REMOTE}/initial_entry_prices.json")
    try:
        init_data = json.loads(init_raw)
    except json.JSONDecodeError:
        init_data = {}

    key = "SOLUSDT_LONG"
    if key not in init_data:
        key = "LINKUSDT_LONG" if "LINKUSDT_LONG" in init_data else next(iter(init_data), None)
    if not key:
        lines.append("HATA: initial_entry_prices boş")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return

    old_entry = float(init_data[key])
    new_entry = round(old_entry * 1.06, 8)
    init_data[key] = new_entry

    lines.append(f"\n========== 2-3) TEST: {key} entry {old_entry} -> {new_entry} (x1.06) ==========")
    run(client, f"cp {REMOTE}/initial_entry_prices.json {REMOTE}/initial_entry_prices.json.bak_defense_test")

    payload = json.dumps(init_data, indent=2, ensure_ascii=False)
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE}/initial_entry_prices.json", "w") as f:
        f.write(payload)
    sftp.close()
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    lines.append("\n========== 4) LOG İZLEME (90s, defense/D1/SOL) ==========")
    run(
        client,
        f"timeout 90 tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'SOLUSDT|LINKUSDT|defense|D1|defense_level' || true",
        timeout=100,
    )

    lines.append("\n========== 5) SONUÇ DOSYALARI ==========")
    run(client, f"grep -E 'SOLUSDT|defense|D1' {REMOTE}/mina_bot.log | tail -20")
    run(client, f"cat {REMOTE}/defense_levels.json")
    run(client, f"cat {REMOTE}/position_states.json")
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); "
        "c.row_factory=sqlite3.Row; "
        "rows=c.execute(\\\"SELECT id,symbol,side,defense_triggered,defense_prices,status FROM trades "
        "WHERE symbol IN ('SOLUSDT','LINKUSDT') AND status='open' ORDER BY id\\\").fetchall(); "
        "print('DERR open SOL/LINK:'); "
        "[print(dict(r)) for r in rows]\""
    ))

    lines.append("\n========== 6) GERİ YÜKLEME ==========")
    run(client, f"mv {REMOTE}/initial_entry_prices.json.bak_defense_test {REMOTE}/initial_entry_prices.json")
    run(client, f"cat {REMOTE}/initial_entry_prices.json")

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
