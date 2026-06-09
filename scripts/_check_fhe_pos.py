#!/usr/bin/env python3
import json, sys
sys.path.insert(0, "/root/MINA_v2")
from backend.config import BinanceConfig
c = BinanceConfig().get_client()
for p in c.futures_position_information():
    if float(p.get("positionAmt", 0)) != 0:
        print(p["symbol"], p["positionSide"], p["positionAmt"], "lev=", p.get("leverage"))
state = json.load(open("/root/MINA_v2/mina_position_state.json"))
for k in ("FHEUSDT", "FHE"):
    if k in state:
        print("state", k, state[k])
