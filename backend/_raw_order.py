import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
import requests, hmac, hashlib, time, os

API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")
BASE       = "https://testnet.binancefuture.com"

def sign(params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return qs + "&signature=" + sig

headers = {"X-MBX-APIKEY": API_KEY}

# Sunucu zamanı al
print("1) Server time...")
r = requests.get(f"{BASE}/fapi/v1/time", timeout=10)
server_ts = r.json()["serverTime"]
print(f"   serverTime: {server_ts}")

# Yerel zaman farkı
local_ts = int(time.time() * 1000)
drift = local_ts - server_ts
print(f"   Yerel drift: {drift}ms")

# Bakiye
print("2) Bakiye...")
params = {"timestamp": server_ts + 500, "recvWindow": 10000}
r = requests.get(f"{BASE}/fapi/v2/balance", params=sign(params), headers=headers, timeout=10)
bal = r.json()
usdt = next((x for x in bal if x.get("asset") == "USDT"), None)
if usdt:
    balance = float(usdt["balance"])
    print(f"   USDT: {balance:.2f}")
else:
    print(f"   Hata: {bal}")
    balance = 0

# Fiyat
print("3) BTC fiyat...")
r = requests.get(f"{BASE}/fapi/v1/ticker/price", params={"symbol": "BTCUSDT"}, timeout=10)
price = float(r.json()["price"])
print(f"   BTC: {price}")

# Emir gönder
print("4) Emir gönder...")
amount = (balance / 10) * 0.20 * 4  # leveraged
qty = round(amount / price, 3)
ts = int(time.time() * 1000)
params = {
    "symbol":       "BTCUSDT",
    "side":         "BUY",
    "positionSide": "LONG",
    "type":         "MARKET",
    "quantity":     qty,
    "timestamp":    ts,
    "recvWindow":   15000,
}
t0 = time.time()
r = requests.post(f"{BASE}/fapi/v1/order", params=sign(params), headers=headers, timeout=30)
elapsed = (time.time() - t0) * 1000
print(f"   HTTP {r.status_code} ({elapsed:.0f}ms)")
print(f"   Yanit: {r.text[:300]}")
