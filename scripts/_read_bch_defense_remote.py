#!/usr/bin/env python3
import json, sqlite3, os
ROOT = "/root/MINA_v2"
def load(fn):
    p = os.path.join(ROOT, fn)
    if not os.path.isfile(p):
        return {}
    with open(p) as f:
        return json.load(f)
defense = load("defense_levels.json")
initial = load("initial_entry_prices.json")
state = load("mina_position_state.json")
print("=== defense_levels.json (BCH) ===")
for k,v in defense.items():
    if "BCH" in k:
        print(f"  {k}: {v}")
if not any("BCH" in k for k in defense):
    print("  (BCHUSDT key yok veya dosya bos)")
print("\n=== full defense_levels.json ===")
print(json.dumps(defense, indent=2))
print("\n=== initial_entry_prices BCH ===")
for k,v in initial.items():
    if "BCH" in k:
        print(f"  {k}: {v}")
print("\n=== mina_position_state BCHUSDT ===")
if isinstance(state, dict):
    if "BCHUSDT" in state:
        print(json.dumps(state["BCHUSDT"], indent=2))
    elif "positions" in state and "BCHUSDT" in state.get("positions", {}):
        print(json.dumps(state["positions"]["BCHUSDT"], indent=2))
    else:
        print(json.dumps({k:v for k,v in state.items() if "BCH" in str(k)}, indent=2))
conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT id,defense_triggered,defense_prices,weighted_avg_price,open_price FROM trades WHERE symbol='BCHUSDT' AND status='open'").fetchone()
print("\n=== DERR open BCH ===")
print(dict(r) if r else "none")
