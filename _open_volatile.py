# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
from config import BinanceConfig, AccountManager
from binance.enums import *
import time

LEVERAGE    = 4

config  = BinanceConfig()
client  = config.get_client()
account = AccountManager(client)
bal = account.get_usdt_balance()
slot_size = bal / 10
MARGIN_USDT = round(slot_size * 0.20, 2)
print(f"Dinamik giris miktari: {MARGIN_USDT} USDT (Bakiye: {bal:.2f} USDT)")

POSITIONS = [
    # LONG — oversold bounce candidates
    ("BOBUSDT",     "LONG"),
    ("AIOTUSDT",    "LONG"),
    ("DYMUSDT",     "LONG"),
    ("ALTUSDT",     "LONG"),
    # SHORT — momentum continuation
    ("AGTUSDT",     "SHORT"),
    ("OBOLUSDT",    "SHORT"),
    ("PHAUSDT",     "SHORT"),
    ("SKYAIUSDT",   "SHORT"),
    # HEDGE — both sides
    ("PLAYUSDT",    "LONG"),
    ("PLAYUSDT",    "SHORT"),
    # 11th slot — limit test
    ("BTCUSDT",     "LONG"),
]

print(f"Margin/pozisyon: {MARGIN_USDT} USDT | Kaldırac: {LEVERAGE}x")
print()

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

results = []

print(f"{'#':>3}  {'Symbol':<12} {'Side':<6}  Sonuc")
print("-" * 55)

for i, (symbol, side) in enumerate(POSITIONS, 1):
    # Leverage
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass

    # Margin type
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    # Price
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price  = float(ticker['price'])
    except Exception as e:
        msg = f"HATA (fiyat): {str(e)[:60]}"
        print(f"{i:>3}. {symbol:<12} {side:<6}  {msg}")
        results.append((symbol, side, False, msg))
        continue

    prec = get_precision(symbol)
    qty  = round((MARGIN_USDT * LEVERAGE) / price, prec)
    order_side   = SIDE_BUY if side == 'LONG' else SIDE_SELL
    position_side = 'LONG' if side == 'LONG' else 'SHORT'

    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
            positionSide=position_side
        )
        msg = f"OK  OrderID:{order['orderId']}  Qty:{qty}  @{round(price,4)}"
        print(f"{i:>3}. {symbol:<12} {side:<6}  {msg}")
        results.append((symbol, side, True, msg))
    except Exception as e:
        err = str(e)
        if '-1109' in err:
            msg = "ATLANDI (-1109 hedge mode desteklenmiyor)"
        elif '-4005' in err:
            msg = f"HATA (-4005 qty cok buyuk): qty={qty}"
        elif '-1003' in err:
            msg = "HATA (-1003 rate limit)"
        else:
            msg = f"HATA: {err[:70]}"
        print(f"{i:>3}. {symbol:<12} {side:<6}  {msg}")
        results.append((symbol, side, False, msg))

    time.sleep(0.4)

# Summary
print()
print("=" * 55)
print("OZET")
print("=" * 55)
ok     = [(s, d, m) for s, d, ok_, m in results if ok_]
fail   = [(s, d, m) for s, d, ok_, m in results if not ok_]
print(f"Acildi:    {len(ok)}")
print(f"Basarisiz: {len(fail)}")
if fail:
    print("\nBasarisizlar:")
    for s, d, m in fail:
        print(f"  {s} {d}: {m}")
