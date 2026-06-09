#!/usr/bin/env python3
import json, sys
sys.path.insert(0, "/root/MINA_v2")
from backend.config import BinanceConfig
from mina_position_manager import MinaPositionManager
import mina_trading as mt

client = BinanceConfig().get_client()
mark = float(client.futures_mark_price(symbol="FHEUSDT")["markPrice"])
entry = mark / 0.87
print("mark", mark, "fake_entry", entry)
print("d1_hit", mark <= entry * 0.95, "line", entry * 0.95)
print("d2_hit", mark <= entry * 0.88, "line", entry * 0.88)

# leverage strategy
from mina_dashboard_settings import leverage_strategy_mode
print("2x strategy", leverage_strategy_mode(2))

# journal defense
from mina_trading_journal import TradingJournal
j = TradingJournal("/root/MINA_v2/mina_trading_journal.db")
# find open trade for FHE
import sqlite3
c = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
rows = c.execute("SELECT id,symbol,side,leverage,status,defense_level FROM trades WHERE symbol='FHEUSDT' ORDER BY id DESC LIMIT 3").fetchall()
print("trades", rows)
c.close()

# engine lock
try:
    print("engine.lock", open("/root/MINA_v2/engine.lock").read().strip())
except Exception as e:
    print("engine", e)

# simulate evaluate
balance = float([a for a in client.futures_account_balance() if a["asset"]=="USDT"][0]["balance"])
slot = balance / 10
mina = MinaPositionManager(client, slot_size=slot, journal=j)
pos = None
for p in client.futures_position_information(symbol="FHEUSDT"):
    if float(p.get("positionAmt",0)) != 0:
        pos = {
            "symbol": "FHEUSDT",
            "side": "LONG",
            "amount": abs(float(p["positionAmt"])),
            "entry_price": float(p["entryPrice"]),
            "leverage": int(p.get("leverage") or 2),
            "slotType": "motor",
        }
print("pos", pos)

# temporarily set initial entry
orig = mt.load_json(mt.INITIAL_PRICE_FILE)
mt.save_json(mt.INITIAL_PRICE_FILE, {**orig, "FHEUSDT_LONG": entry})

if pos:
    act = mina.evaluate_position(pos, mark)
    print("evaluate_action", act)

mt.save_json(mt.INITIAL_PRICE_FILE, orig)
