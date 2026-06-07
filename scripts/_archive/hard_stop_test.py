#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hard Stop (D99) testi — BTC motor pozisyonu."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"
OUT = os.path.join(_ROOT, "hard_stop_test_out.txt")
lines: list[str] = []


def run(client, cmd: str, timeout: int = 180) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    lines.append(f"$ {cmd}\n{out}")
    if err.strip():
        lines.append(f"STDERR:\n{err}")
    return out


REMOTE_TEST = r'''
import json, requests, shutil, subprocess, sqlite3, time, sys
ROOT = "/root/MINA_v2"
PY = f"{ROOT}/venv/bin/python"

def load(fn):
    with open(f"{ROOT}/{fn}") as f:
        return json.load(f)

def save(fn, data):
    with open(f"{ROOT}/{fn}", "w") as f:
        json.dump(data, f, indent=2)

sym = "BTCUSDT"
key = "BTCUSDT_LONG"

print("=== 1) BTC motor pozisyonu ac ===")
db = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
open_row = db.execute("SELECT id FROM trades WHERE symbol=? AND status='open'", (sym,)).fetchone()
db.close()
if not open_row:
    r = subprocess.run(
        [PY, f"{ROOT}/scripts/manual_open.py", "--symbol", sym, "--side", "LONG", "--leverage", "4", "--source", "haluk"],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr)
    if r.returncode != 0:
        print("manual_open failed, exit", r.returncode)
        sys.exit(1)
    time.sleep(8)
else:
    print(f"BTC zaten acik trade_id={open_row[0]}")
print("\n=== 2) ONCE ===")
print("initial_entry:", json.dumps(load("initial_entry_prices.json"), indent=2))
print("defense:", json.dumps(load("defense_levels.json"), indent=2))

mark = float(requests.get("https://fapi.binance.com/fapi/v1/ticker/price", params={"symbol": sym}, timeout=10).json()["price"])
fake = round(mark / 0.74, 8)
print(f"\n=== 3) Hard stop tetik: mark={mark} entry={fake} (mark/0.74) ===")

shutil.copy(f"{ROOT}/initial_entry_prices.json", f"{ROOT}/initial_entry_prices.json.bak_hs_test")
ie = load("initial_entry_prices.json")
real_entry = ie.get(key, mark)
ie[key] = fake
save("initial_entry_prices.json", ie)
print("patched initial_entry:", ie[key])
dl = load("defense_levels.json")
dl[key] = 3
save("defense_levels.json", dl)
st = load("mina_position_state.json")
s = st.get(sym, {})
s["defense_stage"] = 3
st[sym] = s
save("mina_position_state.json", st)
# journal D3 — D1/D2 atlanir, hard stop tetiklensin
db = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
db.execute("UPDATE trades SET defense_triggered=3 WHERE symbol=? AND status='open'", (sym,))
db.commit()
db.close()
print("defense_levels=3, journal defense_triggered=3")
'''


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)

    # Önce cooldown fix deploy
    sftp = client.open_sftp()
    for rel in ("mina_coin_lock.py", "mina_position_manager.py", "main.py"):
        sftp.put(os.path.join(_ROOT, rel), f"{REMOTE}/{rel}")
    with sftp.file(f"{REMOTE}/scripts/_hs_test_prep.py", "w") as f:
        f.write(REMOTE_TEST)
    sftp.close()

    run(client, "systemctl restart mina-engine.service")
    run(client, "sleep 5")
    run(client, f"{REMOTE}/venv/bin/python {REMOTE}/scripts/_hs_test_prep.py")

    lines.append("\n=== tail 120s ===")
    run(
        client,
        f"timeout 120 tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'BTCUSDT|defense|Hard|HARD|D99|cooldown|FAILED' || true",
        timeout=130,
    )

    run(client, f"grep -iE 'BTCUSDT.*defense|Hard|HARD|D99|cooldown' {REMOTE}/mina_bot.log | tail -15")
    run(client, f"cat {REMOTE}/coin_cooldown.json 2>/dev/null || echo '(yok)'")
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sys; sys.path.insert(0,'/root/MINA_v2'); "
        "from mina_coin_lock import coin_cooldown_remaining, check_motor_can_open; "
        "print('cooldown_remaining_s', coin_cooldown_remaining('BTCUSDT')); "
        "print('can_open', check_motor_can_open('BTCUSDT'))\""
    ))
    run(client, (
        f"{REMOTE}/venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db'); "
        "c.row_factory=sqlite3.Row; "
        "rows=c.execute(\\\"SELECT id,symbol,status,close_reason,close_time,pnl_usdt FROM trades "
        "WHERE symbol='BTCUSDT' ORDER BY id DESC LIMIT 2\\\").fetchall(); "
        "[print(dict(r)) for r in rows]\""
    ))

    lines.append("\n=== RESTORE ===")
    run(client, (
        f"test -f {REMOTE}/initial_entry_prices.json.bak_hs_test && "
        f"mv {REMOTE}/initial_entry_prices.json.bak_hs_test {REMOTE}/initial_entry_prices.json; "
        f"cat {REMOTE}/initial_entry_prices.json"
    ))

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
