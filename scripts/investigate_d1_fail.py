#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run(cmd):
    print(f"\n=== {cmd} ===")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out if out.strip() else "(bos)")

run("date -u")
run("systemctl cat mina-engine.service 2>/dev/null | head -25")
run("journalctl -u mina-engine.service --since '2026-06-05 19:13:00' --until '2026-06-05 19:15:00' --no-pager 2>&1")
run("journalctl -u mina-engine.service -n 50 --no-pager 2>&1")
run("grep '2026-06-05 19:13' /root/MINA_v2/mina_bot.log")
run("grep -E 'D1|defense|ekleme|add_qty|BTCUSDT' /root/MINA_v2/mina_bot.log | grep '2026-06-05 19:'")

# stdout from engine if logged elsewhere
import os
for p in ["/root/MINA_v2/engine_stdout.log", "/var/log/mina-engine.log"]:
    if os.path.isfile(p):
        run(f"grep '19:13' {p} | tail -20")

# Binance position after D1 attempt
run("/root/MINA_v2/venv/bin/python - <<'PY'\nimport sys\nsys.path.insert(0,'/root/MINA_v2')\nfrom backend.config import BinanceConfig\nc=BinanceConfig().get_client()\nfor p in c.futures_position_information(symbol='BTCUSDT'):\n if float(p['positionAmt'])!=0:\n  print({k:p[k] for k in ('positionAmt','entryPrice','isolatedMargin','leverage')})\nPY")

run("journalctl -u mina-engine.service --since '2026-06-05 19:12:00' --until '2026-06-05 19:17:00' --no-pager 2>&1 | wc -l")
run("journalctl -u mina-engine.service --since '2026-06-05 19:12:00' --until '2026-06-05 19:17:00' --no-pager 2>&1")

# simulate _round_quantity for D1 at 19:13 mark
run("""/root/MINA_v2/venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'/root/MINA_v2')
from backend.config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal
c=BinanceConfig().get_client()
a=AccountManager(c)
slot=a.calculate_slot_size()
mark=59189.09  # approx at investigation time
add_usdt=slot/5
m=MinaPositionManager(c, slot, journal=TradingJournal('/root/MINA_v2/mina_trading_journal.db'))
add_qty=m._round_quantity(add_usdt/mark, 'BTCUSDT')
print(f'slot={slot} add_usdt={add_usdt} add_qty={add_qty} zero={add_qty<=0}')
# journal defense
import sqlite3
r=sqlite3.connect('/root/MINA_v2/mina_trading_journal.db').execute("SELECT id,defense_triggered FROM trades WHERE symbol='BTCUSDT' AND side='LONG' AND status='open'").fetchone()
print('open trade:', r)
PY""")

import json, os
print('\n=== defense_levels ===')
print(open('/root/MINA_v2/defense_levels.json').read() if os.path.isfile('/root/MINA_v2/defense_levels.json') else 'yok')
