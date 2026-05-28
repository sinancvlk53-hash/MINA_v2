# -*- coding: utf-8 -*-
import sys, os, time
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2')
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2\\backend')
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('C:\\Users\\User\\Desktop\\MINA_v2\\.env')

from binance.enums import *
from config import BinanceConfig, AccountManager

LEVERAGE = 4

LONGS  = ['RAVEUSDT']
SHORTS = ['PHAUSDT']
HEDGE  = []

# Build full order list: (symbol, side)
orders = []
for s in LONGS:
    orders.append((s, 'LONG'))
for s in SHORTS:
    orders.append((s, 'SHORT'))
for s in HEDGE:
    orders.append((s, 'LONG'))
    orders.append((s, 'SHORT'))


_exchange_cache = {}

def get_symbol_info(client, symbol):
    """precision ve max_qty döndür (cache'li)"""
    if symbol in _exchange_cache:
        return _exchange_cache[symbol]
    info = client.futures_exchange_info()
    for s in info['symbols']:
        sym = s['symbol']
        prec, max_qty = 3, float('inf')
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = float(f['stepSize'])
                step_str = str(step).rstrip('0')
                prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
            if f['filterType'] == 'MARKET_LOT_SIZE':
                mq = float(f['maxQty'])
                if mq > 0:
                    max_qty = mq
        _exchange_cache[sym] = (prec, max_qty)
    return _exchange_cache.get(symbol, (3, float('inf')))


def get_price(client, symbol):
    """Fiyat al — ticker yoksa mark price'a fallback"""
    try:
        r = client.futures_symbol_ticker(symbol=symbol)
        if isinstance(r, dict) and 'price' in r:
            return float(r['price'])
        if isinstance(r, list):
            for item in r:
                if item.get('symbol') == symbol:
                    return float(item['price'])
    except Exception:
        pass
    try:
        r = client.futures_mark_price(symbol=symbol)
        if isinstance(r, dict):
            return float(r.get('markPrice') or r.get('price'))
        if isinstance(r, list):
            for item in r:
                if item.get('symbol') == symbol:
                    return float(item['markPrice'])
    except Exception:
        pass
    raise ValueError(f"{symbol} icin fiyat alinamadi")


def open_position(client, account, symbol, side):
    bal    = account.get_usdt_balance()
    margin = round(bal / 10 / 5, 2)

    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    try:
        price = get_price(client, symbol)
    except Exception as e:
        return False, str(e)

    prec, max_qty = get_symbol_info(client, symbol)
    qty   = round((margin * LEVERAGE) / price, prec)
    oside = SIDE_BUY if side == 'LONG' else SIDE_SELL
    pside = 'LONG'   if side == 'LONG' else 'SHORT'

    # chunk if qty > max_qty (-4005 prevention)
    if qty <= max_qty:
        chunks = [qty]
    else:
        chunk = round(max_qty, prec)
        chunks, remaining = [], qty
        while remaining > 0:
            c = round(min(chunk, remaining), prec)
            if c == 0:
                break
            chunks.append(c)
            remaining = round(remaining - c, prec)

    order_ids = []
    try:
        for c in chunks:
            order = client.futures_create_order(
                symbol=symbol, side=oside,
                type=ORDER_TYPE_MARKET,
                quantity=c, positionSide=pside,
            )
            order_ids.append(str(order['orderId']))
            time.sleep(0.1)
    except Exception as e:
        err = str(e)
        if '-1109' in err:
            return False, "ATLANDI (-1109 hedge mode kapali)"
        return False, err[:120]

    ids = ', '.join(order_ids)
    chunk_note = f" ({len(chunks)} emir)" if len(chunks) > 1 else ""
    return True, f"OrderID:{ids} Qty:{qty}{chunk_note} @{round(price, 4)}"


def main():
    config  = BinanceConfig()
    client  = config.get_client()
    account = AccountManager(client)

    bal = account.get_usdt_balance()
    margin_per = round(bal / 10 / 5, 2)
    print(f"Bakiye: ${bal:.2f} | Pozisyon basina margin: ${margin_per:.2f} | Kaldirac: {LEVERAGE}x")
    print(f"Toplam pozisyon: {len(orders)}\n")

    results = {'ok': [], 'fail': []}

    for symbol, side in orders:
        ok, detail = open_position(client, account, symbol, side)
        icon = 'OK' if ok else 'FAIL'
        print(f"[{icon}] {symbol:15s} {side:5s} | {detail}")
        if ok:
            results['ok'].append(f"{symbol} {side}")
        else:
            results['fail'].append(f"{symbol} {side}: {detail}")
        time.sleep(0.4)

    print(f"\n=== OZET ===")
    print(f"Acilan : {len(results['ok'])}/{len(orders)}")
    if results['fail']:
        print(f"Basarisiz ({len(results['fail'])}):")
        for f in results['fail']:
            print(f"  - {f}")


if __name__ == '__main__':
    main()
