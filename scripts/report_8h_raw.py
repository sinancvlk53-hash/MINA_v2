#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Son 8 saat ham rapor — sunucuda çalıştır."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"

REMOTE_SCRIPT = r'''
ROOT="/root/MINA_v2"
echo "========== 1) mina_bot.log grep (tail -30) =========="
grep -E 'take_profit|trailing_stop|defense|stop_loss|açıldı|kapandı|D2 Time Stop|kill' "$ROOT/mina_bot.log" 2>/dev/null | tail -30 || echo "(grep hata veya dosya yok)"

echo ""
echo "========== 2) DERR kapanan işlemler (close_time >= 2026-06-06 16:00 UTC) =========="
cd "$ROOT" && /root/MINA_v2/venv/bin/python - <<'PYEOF'
import sqlite3
conn = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute(
    "SELECT symbol, side, close_reason, pnl_usdt, close_time FROM trades "
    "WHERE close_time >= '2026-06-06 16:00' ORDER BY close_time"
)
rows = cur.fetchall()
if not rows:
    print("(no rows)")
else:
    cols = rows[0].keys()
    print("  ".join(cols))
    for r in rows:
        print("  ".join(str(r[c]) if r[c] is not None else "" for c in cols))
conn.close()
PYEOF

echo ""
echo "========== 3) Merter DCA log (tail -20) =========="
tail -20 "$ROOT/signal_bot/merter_dca.log" 2>/dev/null || echo "(log yok)"

echo ""
echo "========== 4) Açık pozisyonlar (sembol, yön, giriş, mark, PnL, ROE) =========="
cd "$ROOT" && /root/MINA_v2/venv/bin/python - <<'PYEOF'
import os, sys, json
ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from config import BinanceConfig
import sqlite3

c = BinanceConfig().get_client()
positions = [p for p in c.futures_position_information() if float(p.get("positionAmt") or 0) != 0]

# initial_margin from DERR for ROE
margins = {}
try:
    conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT symbol, side, initial_margin FROM trades WHERE status='open'"):
        margins[(r["symbol"], r["side"])] = float(r["initial_margin"] or 0)
    conn.close()
except Exception as e:
    print(f"DERR margin okuma hatasi: {e}", file=sys.stderr)

print(f"{'symbol':<16} {'side':<6} {'entry':<14} {'mark':<14} {'pnl_usdt':<12} {'roe_pct':<10}")
print("-" * 72)
for p in sorted(positions, key=lambda x: x["symbol"]):
    sym = p["symbol"]
    amt = float(p["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    upnl = float(p.get("unRealizedProfit") or 0)
    im = margins.get((sym, side), 0)
    roe = (upnl / im * 100) if im > 0 else float(p.get("roe") or 0) * 100 if p.get("roe") else 0
    print(f"{sym:<16} {side:<6} {entry:<14.6g} {mark:<14.6g} {upnl:<+12.4f} {roe:<+10.2f}")
if not positions:
    print("(acik pozisyon yok)")
PYEOF

echo ""
echo "========== 5) Global risk limiti =========="
ls "$ROOT/daily_loss_kill.flag" 2>/dev/null && echo 'KİLİT AKTİF' || echo 'Normal'

echo ""
echo "========== 6) Servis durumları =========="
systemctl is-active mina-engine mina-listener mina-merter-dca mina-queue-watcher mina-dashboard-ws mina-dashboard-vite mina-binance-listings mina-upbit-listings 2>&1
'''


def main():
    pwd = require_ssh_pass()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=30)
    try:
        stdin, stdout, stderr = client.exec_command(REMOTE_SCRIPT, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out, end="")
        if err.strip():
            print(err, file=sys.stderr, end="")
        print(f"\n[exit={stdout.channel.recv_exit_status()}]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
