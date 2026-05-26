import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
import time

config = BinanceConfig()
client = config.get_client()

print("1) Ping...")
t0 = time.time()
r = client.futures_ping()
print(f"   OK ({(time.time()-t0)*1000:.0f}ms): {r}")

print("2) Server time...")
t0 = time.time()
st = client.futures_time()
print(f"   OK ({(time.time()-t0)*1000:.0f}ms): {st}")

print("3) BTC ticker...")
t0 = time.time()
ticker = client.futures_symbol_ticker(symbol="BTCUSDT")
print(f"   OK ({(time.time()-t0)*1000:.0f}ms): {ticker['price']}")

print("4) Balance...")
t0 = time.time()
bal = client.futures_account_balance()
usdt = next(x for x in bal if x["asset"] == "USDT")
print(f"   OK ({(time.time()-t0)*1000:.0f}ms): {usdt['balance']} USDT")

print("\nBaglanti saglam.")
