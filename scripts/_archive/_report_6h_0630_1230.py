#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ham 6 saat raporu — 2026-06-06 06:30–12:30 UTC."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import paramiko
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

R = "/root/MINA_v2"
PASS = require_ssh_pass()

SECTIONS = [
    (
        "MOTOR LOG",
        f"grep -E 'take_profit|trailing_stop|defense|stop_loss|açıldı|kapandı|D2 Time Stop|kill' "
        f"{R}/mina_bot.log 2>/dev/null | grep '2026-06-06 0[6-9]\\|2026-06-06 1[0-2]' || true",
    ),
    (
        "DERR kapanan işlemler",
        f"""{R}/venv/bin/python - <<'PY'
import sqlite3
conn = sqlite3.connect("{R}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT symbol, side, close_reason, pnl_usdt, close_time FROM trades "
    "WHERE close_time >= '2026-06-06 06:30' ORDER BY close_time"
).fetchall()
for r in rows:
    print(f"{{r['symbol']}}\\t{{r['side']}}\\t{{r['close_reason']}}\\t{{r['pnl_usdt']}}\\t{{r['close_time']}}")
if not rows:
    print("(satır yok)")
conn.close()
PY""",
    ),
    (
        "MERTER DCA LOG",
        f"grep '2026-06-06T0[6-9]\\|2026-06-06T1[0-2]' {R}/signal_bot/merter_dca.log 2>/dev/null || "
        f"(test -f {R}/signal_bot/merter_dca.log && echo '(eşleşen satır yok)' || echo 'merter_dca.log yok')",
    ),
    (
        "HALUK SİNYAL (tail -20)",
        f"grep '2026-06-06 0[6-9]\\|2026-06-06 1[0-2]' {R}/signal_bot/signals_log.txt 2>/dev/null | tail -20 || "
        f"(test -f {R}/signal_bot/signals_log.txt && echo '(eşleşen satır yok)' || echo 'signals_log.txt yok')",
    ),
    (
        "AÇIK POZİSYONLAR",
        f"""{R}/venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, "{R}")
sys.path.insert(0, "{R}/backend")
os.chdir("{R}")
from dotenv import load_dotenv
load_dotenv("{R}/.env")
from config import BinanceConfig
client = BinanceConfig().get_client()
raw = client.futures_position_information()
print("symbol\\tside\\tentry\\tmark\\tpnl_usdt\\troe_pct")
count = 0
for p in raw:
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    count += 1
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    pnl = float(p.get("unRealizedProfit") or 0)
    iso = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
    lev = int(p.get("leverage") or 4)
    if iso <= 0 and entry > 0:
        iso = abs(amt) * entry / max(lev, 1)
    roe = (pnl / iso * 100) if iso > 0 else 0.0
    print(f"{{p['symbol']}}\\t{{side}}\\t{{entry:.8f}}\\t{{mark:.8f}}\\t{{pnl:+.4f}}\\t{{roe:+.2f}}")
if count == 0:
    print("(açık pozisyon yok)")
PY""",
    ),
    (
        "GLOBAL RİSK LİMİTİ",
        f"ls {R}/daily_loss_kill.flag 2>/dev/null && echo 'KİLIT AKTİF' || echo 'Normal'",
    ),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=PASS, timeout=30)

    for title, cmd in SECTIONS:
        print("=" * 80)
        print(title)
        print("=" * 80)
        print(f"$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
        print("-" * 80)
        _, stdout, stderr = c.exec_command(cmd, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err.strip():
            print(err, end="" if err.endswith("\n") else "\n")
        if not out.strip() and not err.strip():
            print("(çıktı yok)")
        print()

    c.close()


if __name__ == "__main__":
    main()
