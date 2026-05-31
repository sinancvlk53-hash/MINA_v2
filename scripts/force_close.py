import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
from config import BinanceConfig
from binance.enums import *

config = BinanceConfig()
client = config.get_client()

positions = client.futures_position_information()
open_pos = [p for p in positions if float(p['positionAmt']) != 0]

print(f"Açık pozisyon: {len(open_pos)}")

for p in open_pos:
    symbol = p['symbol']
    amt = float(p['positionAmt'])
    side = 'LONG' if amt > 0 else 'SHORT'
    close_side = SIDE_SELL if amt > 0 else SIDE_BUY
    quantity = abs(amt)

    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=close_side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide=side
        )
        print(f"✅ {symbol} {side} kapatıldı — OrderID: {order['orderId']}")
    except Exception as e:
        print(f"HATA {symbol} {side}: {e}")
