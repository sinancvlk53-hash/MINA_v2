import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from binance.enums import *
import time

config = BinanceConfig()
client = config.get_client()

# Açık emirler var mı? (timeout'ta açılmış olabilir)
print("1) Bekleyen/açık emirler kontrol...")
orders = client.futures_get_open_orders()
print(f"   Açık emir: {len(orders)}")
for o in orders:
    print(f"   {o['symbol']} {o['side']} {o['type']} qty:{o['origQty']} status:{o['status']}")

# Açık pozisyon var mı?
print("2) Pozisyonlar kontrol...")
positions = client.futures_position_information()
open_pos = [p for p in positions if float(p["positionAmt"]) != 0]
print(f"   Açık pozisyon: {len(open_pos)}")

# recvWindow ile tek emir
print("3) recvWindow=10000 ile emir dene...")
bal = client.futures_account_balance()
usdt = float(next(x for x in bal if x["asset"] == "USDT")["balance"])
amount_usdt = (usdt / 10) * 0.20
ticker = client.futures_symbol_ticker(symbol="BTCUSDT")
price = float(ticker["price"])
quantity = round((amount_usdt * 4) / price, 3)

try:
    t0 = time.time()
    order = client.futures_create_order(
        symbol="BTCUSDT",
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=quantity,
        positionSide='LONG',
        recvWindow=10000
    )
    print(f"   BASARILI ({(time.time()-t0)*1000:.0f}ms): OrderID={order['orderId']}")
except Exception as e:
    print(f"   HATA: {e}")

print("\nTANI TAMAMLANDI.")
