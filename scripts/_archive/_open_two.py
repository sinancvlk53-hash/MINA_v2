# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
from config import BinanceConfig, AccountManager
from binance.enums import *

config  = BinanceConfig()
client  = config.get_client()
account = AccountManager(client)

balance    = account.get_usdt_balance()
amount_usdt = (balance / 10) * 0.20
leverage   = 4

TO_OPEN = [
    ("MUSDT",    "SHORT"),
    ("NEARUSDT", "SHORT"),
]

def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step = float(f['stepSize'])
                    step_str = str(step).rstrip('0')
                    return len(step_str.split('.')[-1]) if '.' in step_str else 0
    return 3

for symbol, side in TO_OPEN:
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except Exception as e:
        print(f"  Kaldıraç uyarı: {e}")
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    ticker = client.futures_symbol_ticker(symbol=symbol)
    price  = float(ticker['price'])
    prec   = get_precision(symbol)
    qty    = round((amount_usdt * leverage) / price, prec)
    order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL

    try:
        order = client.futures_create_order(
            symbol=symbol, side=order_side,
            type=ORDER_TYPE_MARKET, quantity=qty,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )
        print(f"OK  {symbol} {side}  Qty:{qty}  Margin:{round(amount_usdt,2)}$  @{round(price,6)}  OrderID:{order['orderId']}")
    except Exception as e:
        print(f"HATA  {symbol} {side}  {e}")
