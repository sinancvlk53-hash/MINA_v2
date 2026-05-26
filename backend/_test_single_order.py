import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from binance.enums import *
import time

config = BinanceConfig()
client = config.get_client()

SYMBOL = "BTCUSDT"
SIDE = "LONG"
LEVERAGE = 4

print(f"Test: {SYMBOL} {SIDE} {LEVERAGE}x")

# Kaldıraç
try:
    client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
    print("Kaldıraç OK")
except Exception as e:
    print(f"Kaldıraç: {e}")

# Margin
try:
    client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
    print("Margin ISOLATED OK")
except Exception:
    print("Margin zaten ISOLATED")

# Bakiye
bal = client.futures_account_balance()
usdt = float(next(x for x in bal if x["asset"] == "USDT")["balance"])
slot_size = usdt / 10
amount_usdt = slot_size * 0.20
print(f"Bakiye: {usdt:.2f} USDT → Giriş: {amount_usdt:.2f} USDT")

# Ticker
ticker = client.futures_symbol_ticker(symbol=SYMBOL)
price = float(ticker["price"])
print(f"BTC fiyat: {price}")

# Qty
position_size = amount_usdt * LEVERAGE
quantity = round(position_size / price, 3)
print(f"Quantity: {quantity}")

# Emir — 3 deneme
for attempt in range(1, 4):
    print(f"\nEmir deneme {attempt}/3...")
    try:
        t0 = time.time()
        order = client.futures_create_order(
            symbol=SYMBOL,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='LONG'
        )
        ms = (time.time() - t0) * 1000
        print(f"BASARILI ({ms:.0f}ms)!")
        print(f"  OrderID:  {order['orderId']}")
        print(f"  Status:   {order['status']}")
        print(f"  AvgPrice: {order.get('avgPrice', 'N/A')}")
        break
    except Exception as e:
        print(f"HATA: {e}")
        if attempt < 3:
            print("5 saniye bekleniyor...")
            time.sleep(5)
