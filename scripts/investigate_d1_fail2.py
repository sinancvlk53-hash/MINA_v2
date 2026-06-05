#!/usr/bin/env python3
import subprocess
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run(cmd):
    print(f"\n=== {cmd[:120]} ===")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print((r.stdout or "") + (r.stderr or ""))

run("systemctl status mina-engine.service --no-pager | head -15")
run("journalctl -u mina-engine.service --since '2026-06-05 19:12:17' --no-pager 2>&1 | tail -80")
run("grep '19:1[3-7]' /root/MINA_v2/mina_bot.log")
run("grep -i 'ekleme\\|gercek\\|D1\\|Invalid\\|1109' /root/MINA_v2/mina_bot.log | tail -20")

# try D1 order now
run("""/root/MINA_v2/venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'/root/MINA_v2')
from backend.config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal
from binance.enums import SIDE_BUY, ORDER_TYPE_MARKET
c=BinanceConfig().get_client()
a=AccountManager(c)
slot=a.calculate_slot_size()
mark=float(c.futures_mark_price(symbol='BTCUSDT')['markPrice'])
add_usdt=slot/5
m=MinaPositionManager(c, slot, journal=TradingJournal('/root/MINA_v2/mina_trading_journal.db'))
add_qty=m._round_quantity(add_usdt/mark, 'BTCUSDT')
print(f'add_qty={add_qty} notional={add_qty*mark:.2f}')
try:
    o=c.futures_create_order(symbol='BTCUSDT', side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=add_qty, positionSide='LONG')
    print('ORDER OK', o.get('orderId'), o.get('executedQty'))
except Exception as e:
    print('ORDER FAIL', type(e).__name__, e)
PY""")
