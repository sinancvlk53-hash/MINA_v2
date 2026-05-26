import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from binance.enums import *

config = BinanceConfig()
client = config.get_client()

# Exchange info bir kez çek
exchange_info = client.futures_exchange_info()
precision_map = {}
for s in exchange_info['symbols']:
    for f in s['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step = float(f['stepSize'])
            step_str = str(step).rstrip('0')
            prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
            precision_map[s['symbol']] = prec

positions = client.futures_position_information()
open_pos = [p for p in positions if float(p['positionAmt']) != 0]

print(f"Acik pozisyon: {len(open_pos)}")
if not open_pos:
    print("Temiz - pozisyon yok.")
    sys.exit(0)

ok, fail = 0, []
for p in open_pos:
    symbol = p['symbol']
    side   = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    amt    = abs(float(p['positionAmt']))
    prec   = precision_map.get(symbol, 3)
    qty    = round(amt, prec)
    order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY

    try:
        order = client.futures_create_order(
            symbol=symbol, side=order_side,
            type=ORDER_TYPE_MARKET, quantity=qty,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )
        print(f"  KAPANDI: {symbol} {side} qty={qty} OrderID={order['orderId']}")
        ok += 1
    except Exception as e:
        print(f"  HATA: {symbol} {side} -> {e}")
        fail.append(f"{symbol} {side}")
    time.sleep(0.5)

print(f"\nBasarili: {ok}/{len(open_pos)}")
if fail:
    print(f"Basarisiz: {fail}")
