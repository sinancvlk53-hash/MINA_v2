#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trailing kapanış testi."""
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
OUT = os.path.join(_ROOT, "trailing_test_out.txt")
lines: list[str] = []


def run(client, cmd: str, timeout: int = 130) -> str:
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    lines.append(f"$ {cmd}\n{out}")
    if err.strip():
        lines.append(f"STDERR:\n{err}")
    return out


REMOTE_SCRIPT = r'''
import json, requests, shutil, time
ROOT = "/root/MINA_v2"

def load(fn):
    with open(f"{ROOT}/{fn}") as f:
        return json.load(f)

def save(fn, data):
    with open(f"{ROOT}/{fn}", "w") as f:
        json.dump(data, f, indent=2)

print("=== ONCE ===")
print("max_prices:", json.dumps(load("max_prices.json"), indent=2))
print("tp_levels:", json.dumps(load("tp_levels.json"), indent=2))

sym = "BTCUSDT"
key = "BTCUSDT_LONG"
tp = load("tp_levels.json")
if tp.get("SOLUSDT_LONG", 0) >= 2 and tp.get("BTCUSDT_LONG", 0) < 2:
    sym, key = "SOLUSDT", "SOLUSDT_LONG"

mark = float(requests.get("https://fapi.binance.com/fapi/v1/ticker/price",
                           params={"symbol": sym}, timeout=10).json()["price"])
fake_peak = round(mark / 0.97, 8)
print(f"\n=== TEST {key} mark={mark} peak={fake_peak} ===")

shutil.copy(f"{ROOT}/max_prices.json", f"{ROOT}/max_prices.json.bak_trail_test")
mp = load("max_prices.json")
mp[key] = fake_peak
save("max_prices.json", mp)
print("max_prices after:", json.dumps(mp, indent=2))

tp_changed = False
if int(tp.get(key, 0)) < 2:
    shutil.copy(f"{ROOT}/tp_levels.json", f"{ROOT}/tp_levels.json.bak_trail_test")
    tp[key] = 2
    save("tp_levels.json", tp)
    tp_changed = True
    shutil.copy(f"{ROOT}/mina_position_state.json", f"{ROOT}/mina_position_state.json.bak_trail_test")
    st = load("mina_position_state.json")
    s = st.get(sym, {})
    s["tp1_done"] = True
    s["tp2_done"] = True
    st[sym] = s
    save("mina_position_state.json", st)
    print("tp_levels patched:", tp[key])

print("\n=== WAIT 120s tail ===")
'''


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)

    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE}/scripts/_trail_test_run.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    run(client, f"{REMOTE}/venv/bin/python {REMOTE}/scripts/_trail_test_run.py")

    out = run(
        client,
        f"timeout 120 tail -f {REMOTE}/mina_bot.log 2>/dev/null | grep -E --line-buffered "
        f"'BTCUSDT|SOLUSDT|trailing|Trailing|FAILED' || true",
        timeout=130,
    )
    lines.append(out)

    run(client, f"grep -iE 'trailing|Trailing' {REMOTE}/mina_bot.log | tail -10")
    run(client, (
        f"{REMOTE}/venv/bin/python <<'PY'\n"
        "import os, json, sqlite3\n"
        "from pathlib import Path\n"
        "for line in Path('/root/MINA_v2/.env').read_text().splitlines():\n"
        "    if '=' in line and not line.startswith('#'):\n"
        "        k,v=line.split('=',1); os.environ.setdefault(k.strip(), v.strip())\n"
        "from binance.client import Client\n"
        "c=Client(os.environ['BINANCE_API_KEY'], os.environ['BINANCE_API_SECRET'])\n"
        "for sym in ('BTCUSDT','SOLUSDT'):\n"
        "    pos=[p for p in c.futures_position_information(symbol=sym) if float(p.get('positionAmt',0))!=0]\n"
        "    print(sym, 'Binance:', 'KAPALI' if not pos else pos[0].get('positionAmt'))\n"
        "db=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db')\n"
        "db.row_factory=sqlite3.Row\n"
        "for sym in ('BTCUSDT','SOLUSDT'):\n"
        "    r=db.execute('SELECT id,symbol,status,close_reason,close_time,pnl_usdt FROM trades WHERE symbol=? ORDER BY id DESC LIMIT 1',(sym,)).fetchone()\n"
        "    print('DERR', sym, dict(r) if r else None)\n"
        "PY"
    ))

    lines.append("\n=== RESTORE ===")
    run(client, (
        f"test -f {REMOTE}/max_prices.json.bak_trail_test && "
        f"mv {REMOTE}/max_prices.json.bak_trail_test {REMOTE}/max_prices.json; "
        f"test -f {REMOTE}/tp_levels.json.bak_trail_test && "
        f"mv {REMOTE}/tp_levels.json.bak_trail_test {REMOTE}/tp_levels.json; "
        f"test -f {REMOTE}/mina_position_state.json.bak_trail_test && "
        f"mv {REMOTE}/mina_position_state.json.bak_trail_test {REMOTE}/mina_position_state.json; "
        f"cat {REMOTE}/max_prices.json"
    ))

    client.close()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
