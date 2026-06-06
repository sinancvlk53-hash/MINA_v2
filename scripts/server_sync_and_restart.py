# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Sunucuda sync_reality_from_binance + JSON dump + motor restart."""
import paramiko
import sys

HOST = SSH_HOST
USER = SSH_USER
PASS = require_ssh_pass()
ROOT = "/root/MINA_v2"
VPY = f"{ROOT}/venv/bin/python"

SYNC_PY = r"""
import os, sys, json
sys.path.insert(0, '/root/MINA_v2')
sys.path.insert(0, '/root/MINA_v2/backend')
os.chdir('/root/MINA_v2')
os.environ['MINA_DATA_ROOT'] = '/root/MINA_v2'

from config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal

client = BinanceConfig().get_client()
slot = AccountManager(client).calculate_slot_size()
journal = TradingJournal(db_path='/root/MINA_v2/mina_trading_journal.db')
mina = MinaPositionManager(client, slot, journal=journal, data_root='/root/MINA_v2')
report = mina.sync_reality_from_binance(verbose=True)
print('SYNC_REPORT=' + json.dumps(report, ensure_ascii=False, indent=2))
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

steps = [
    (
        "LABUSDT defense log (once sync)",
        f"grep -i LABUSDT {ROOT}/mina_bot.log | grep -iE 'SAVUNMA|defense|D1|D2|D3|savunma|LABUSDT' | tail -40",
    ),
    (
        "defense_levels.json BEFORE sync",
        f"cat {ROOT}/defense_levels.json",
    ),
    (
        "sync_reality_from_binance",
        f"cd {ROOT} && MINA_DATA_ROOT={ROOT} {VPY} -c {repr(SYNC_PY)}",
    ),
    (
        "initial_entry_prices.json AFTER sync",
        f"cat {ROOT}/initial_entry_prices.json",
    ),
    (
        "defense_levels.json AFTER sync",
        f"cat {ROOT}/defense_levels.json",
    ),
    (
        "restart mina-engine",
        "systemctl restart mina-engine.service && sleep 2 && systemctl is-active mina-engine.service",
    ),
    (
        "motor son log",
        f"tail -n 8 {ROOT}/mina_bot.log",
    ),
]

sys.stdout.reconfigure(encoding="utf-8")
for title, cmd in steps:
    print("=" * 70)
    print(f">>> {title}")
    print(f">>> CMD: {cmd[:200]}...")
    print("=" * 70)
    _, out, err = c.exec_command(cmd, timeout=180)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    if o:
        print(o, end="" if o.endswith("\n") else "\n")
    if e:
        print("STDERR:", e)

c.close()
