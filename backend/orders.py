# -*- coding: utf-8 -*-
"""
MİNA v2 - Order Management
MARKET, LIMIT, STOP_MARKET pozisyon açma
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BinanceConfig, AccountManager
from binance.enums import *


# ═══════════════════════════════════════════════
# SEMBOL FİLTRE CACHE
# ═══════════════════════════════════════════════

_filter_cache = {}

def _get_symbol_filters(client, symbol):
    """LOT_SIZE ve PRICE_FILTER precision'larını cache'li getir"""
    if symbol in _filter_cache:
        return _filter_cache[symbol]

    lot_prec = 3
    price_prec = 2
    exchange_info = client.futures_exchange_info()

    for s in exchange_info['symbols']:
        if s['symbol'] != symbol:
            continue
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_str = str(float(f['stepSize'])).rstrip('0')
                lot_prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
            elif f['filterType'] == 'PRICE_FILTER':
                tick_str = str(float(f['tickSize'])).rstrip('0')
                price_prec = len(tick_str.split('.')[-1]) if '.' in tick_str else 0
        break

    _filter_cache[symbol] = (lot_prec, price_prec)
    return lot_prec, price_prec


# ═══════════════════════════════════════════════
# ANA FONKSİYON
# ═══════════════════════════════════════════════

def open_position(
    client,
    symbol,
    side,
    leverage,
    order_type='MARKET',
    price=None,
    stop_price=None,
    amount_usdt=None
):
    """
    Pozisyon aç: MARKET, LIMIT veya STOP_MARKET

    Args:
        client      : Binance Futures client
        symbol      : Örn. 'BTCUSDT'
        side        : 'LONG' veya 'SHORT'
        leverage    : 1, 2, 3, 4, 5, 10
        order_type  : 'MARKET' | 'LIMIT' | 'STOP_MARKET'
        price       : LIMIT için limit fiyatı
        stop_price  : STOP_MARKET için tetikleyici fiyat
        amount_usdt : None = otomatik (bakiye/10 * 0.20)

    Returns:
        (True, order_dict) | (False, hata_mesajı)

    Kullanım:
        # Anlık fiyattan aç
        ok, res = open_position(client, 'BTCUSDT', 'LONG', 4)

        # 80000'e limit order koy
        ok, res = open_position(client, 'BTCUSDT', 'LONG', 4,
                                order_type='LIMIT', price=80000)

        # 75000'de tetiklenecek stop
        ok, res = open_position(client, 'BTCUSDT', 'LONG', 4,
                                order_type='STOP_MARKET', stop_price=75000)
    """
    if order_type not in ('MARKET', 'LIMIT', 'STOP_MARKET'):
        return False, f"Geçersiz order_type: '{order_type}'. MARKET | LIMIT | STOP_MARKET olmalı"
    if order_type == 'LIMIT' and price is None:
        return False, "LIMIT order için 'price' parametresi gerekli"
    if order_type == 'STOP_MARKET' and stop_price is None:
        return False, "STOP_MARKET order için 'stop_price' parametresi gerekli"

    try:
        # Bakiye ve margin miktarı
        if amount_usdt is None:
            account = AccountManager(client)
            balance = account.get_usdt_balance()
            amount_usdt = (balance / 10) * 0.20

        # Kaldıraç ayarla
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
        except Exception:
            pass  # Zaten aynı kaldıraçsa hata verir, sorun yok

        # Margin tipi
        try:
            client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
        except Exception:
            pass  # Zaten ISOLATED ise hata verir, sorun yok

        # Precision değerleri
        lot_prec, price_prec = _get_symbol_filters(client, symbol)

        # Quantity hesabı için referans fiyat
        if order_type == 'LIMIT':
            ref_price = float(price)
        elif order_type == 'STOP_MARKET':
            ref_price = float(stop_price)
        else:  # MARKET
            ticker = client.futures_symbol_ticker(symbol=symbol)
            ref_price = float(ticker['price'])

        quantity = round((amount_usdt * leverage) / ref_price, lot_prec)

        # Order parametrelerini oluştur
        params = {
            'symbol':       symbol,
            'side':         SIDE_BUY if side == 'LONG' else SIDE_SELL,
            'type':         order_type,
            'quantity':     quantity,
            'positionSide': 'LONG' if side == 'LONG' else 'SHORT',
        }

        if order_type == 'LIMIT':
            params['price']       = round(float(price), price_prec)
            params['timeInForce'] = 'GTC'

        elif order_type == 'STOP_MARKET':
            params['stopPrice'] = round(float(stop_price), price_prec)

        order = client.futures_create_order(**params)
        return True, order

    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("MİNA v2 - ORDERS TEST")
    print("=" * 60)

    config = BinanceConfig()
    client = config.get_client()

    ticker = client.futures_symbol_ticker(symbol='BTCUSDT')
    current_price = float(ticker['price'])
    print(f"\nBTC Fiyatı: ${current_price:,.2f}")

    print("\n--- TEST 1: MARKET ---")
    ok, result = open_position(client, 'BTCUSDT', 'LONG', 4)
    if ok:
        print(f"✅ OrderID: {result['orderId']} | Qty: {result['origQty']} | Status: {result['status']}")
    else:
        print(f"❌ {result}")

    print("\n--- TEST 2: LIMIT (mevcut fiyatın %1 altı) ---")
    limit_price = round(current_price * 0.99, 1)
    ok, result = open_position(client, 'BTCUSDT', 'LONG', 4,
                               order_type='LIMIT', price=limit_price)
    if ok:
        print(f"✅ OrderID: {result['orderId']} | Price: ${limit_price} | Status: {result['status']}")
    else:
        print(f"❌ {result}")

    print("\n--- TEST 3: STOP_MARKET (mevcut fiyatın %2 üstü) ---")
    stop_price = round(current_price * 1.02, 1)
    ok, result = open_position(client, 'BTCUSDT', 'LONG', 4,
                               order_type='STOP_MARKET', stop_price=stop_price)
    if ok:
        print(f"✅ OrderID: {result['orderId']} | StopPrice: ${stop_price} | Status: {result['status']}")
    else:
        print(f"❌ {result}")

    print("\n" + "=" * 60)
    print("✅ TEST TAMAMLANDI!")
    print("=" * 60)
