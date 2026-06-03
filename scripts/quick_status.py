#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from binance.client import Client
from dotenv import load_dotenv
load_dotenv()
Client.ping = lambda self: {}
c = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"), testnet=True)
bal = next(x for x in c.futures_account_balance() if x["asset"] == "USDT")
print(f"BALANCE_USDT={float(bal['balance']):.4f}")
n = 0
for p in c.futures_position_information():
    amt = float(p.get("positionAmt", 0))
    if amt != 0:
        n += 1
        side = "LONG" if amt > 0 else "SHORT"
        print(f"  {p['symbol']} {side} amt={amt} margin={p.get('isolatedMargin')}")
print(f"OPEN_COUNT={n}")
