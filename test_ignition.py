# -*- coding: utf-8 -*-
"""
MINA v2 - Test Ignition

Bu script Binance Testnet'e aşağıdaki pozisyonları açar:
- 4x kaldıraç
- ISOLATED marjin
- Her pozisyon için ~20 USDT margin (notional ~80 USDT)
- LABUSDT, FLNCUSDT, VICUSDT, HOMEUSDT LONG
- CLOUSDT, RIFUSDT, NOMUSDT, NEARUSDT SHORT
- PARTIUSDT hem LONG hem SHORT
- BTCUSDT LONG stres testi
"""

from decimal import Decimal, ROUND_DOWN
from time import sleep

from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

from backend.config import BinanceConfig

ENTRY_MARGIN_USDT = Decimal('20.0')
LEVERAGE = 4
LONG_SYMBOLS = ['LABUSDT', 'FLNCUSDT', 'VICUSDT', 'HOMEUSDT']
SHORT_SYMBOLS = ['CLOUSDT', 'RIFUSDT', 'NOMUSDT', 'NEARUSDT']
HEDGE_SYMBOL = 'PARTIUSDT'
STRESS_SYMBOL = 'BTCUSDT'


def get_symbol_filters(client):
    info = client.futures_exchange_info()
    step_sizes = {}
    for symbol_info in info['symbols']:
        symbol = symbol_info['symbol']
        for f in symbol_info.get('filters', []):
            if f.get('filterType') == 'LOT_SIZE':
                step_sizes[symbol] = Decimal(f['stepSize'])
                break
    return step_sizes


def format_quantity(raw_qty: Decimal, step_size: Decimal) -> Decimal:
    if step_size <= 0:
        return raw_qty.quantize(Decimal('0.0001'), rounding=ROUND_DOWN)

    precision = abs(step_size.as_tuple().exponent)
    quant = Decimal('1').scaleb(-precision)
    return raw_qty.quantize(quant, rounding=ROUND_DOWN)


def ensure_hedge_mode(client):
    try:
        client.futures_change_position_mode(dualSidePosition='true')
        print('✅ Hedge modu aktif edildi (veya zaten aktif).')
    except Exception as exc:
        print(f'⚠️ Hedge modu ayarlanamadı: {exc}')


def set_isolated_leverage(client, symbol: str):
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
        print(f'   ✅ {symbol} için ISOLATED marjin ayarlandı.')
    except Exception as exc:
        print(f'   ⚠️ {symbol} isolated margin ayarı başarısız: {exc}')

    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        print(f'   ✅ {symbol} için {LEVERAGE}x kaldıraç ayarlandı.')
    except Exception as exc:
        print(f'   ⚠️ {symbol} kaldıraç ayarı başarısız: {exc}')


def get_notional_quantity(client, symbol: str, usd_size: Decimal, step_size: Decimal) -> Decimal:
    ticker = client.futures_symbol_ticker(symbol=symbol)
    price = Decimal(str(ticker['price']))
    raw_qty = (usd_size * LEVERAGE) / price
    quantity = format_quantity(raw_qty, step_size)
    if quantity <= 0:
        raise ValueError(f'Quantity 0 veya negatif oldu: {symbol} fiyat={price} miktar={raw_qty}')
    return quantity, price


def place_market_order(client, symbol: str, side: str, position_side: str, quantity: Decimal):
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=float(quantity),
            positionSide=position_side
        )
        print(f'✅ {symbol} {position_side} açıldı: side={side} qty={quantity}')
        print(f'   Order ID: {order.get("orderId")}')
        return order
    except Exception as exc:
        print(f'❌ {symbol} {position_side} açma hatası: {exc}')
        return None


def open_position(client, symbol: str, position_side: str, step_sizes: dict) -> bool:
    print(f'\n--- {symbol} {position_side} için hazırlık ---')
    try:
        set_isolated_leverage(client, symbol)
        sleep(0.2)

        step_size = step_sizes.get(symbol)
        if step_size is None:
            raise RuntimeError(f'Step size bulunamadı: {symbol}')

        quantity, price = get_notional_quantity(client, symbol, ENTRY_MARGIN_USDT, step_size)
        order_side = SIDE_BUY if position_side == 'LONG' else SIDE_SELL
        order = place_market_order(client, symbol, order_side, position_side, quantity)
        if order:
            notional = (quantity * Decimal(str(price))).quantize(Decimal('0.01'))
            print(f'   🔥 Pozisyon notional: {notional} USDT  (yaklaşık 20 USDT marjin / 4x)')
            return True
        return False
    except Exception as exc:
        print(f'❌ {symbol} için işlem yapılırken hata: {exc}')
        return False


def try_open_with_backup(client, primary: str, backup: str, position_side: str, step_sizes: dict) -> None:
    success = open_position(client, primary, position_side, step_sizes)
    if success:
        return

    print(f'⚠️ {primary} açma başarısız oldu, yedeğe geçiliyor: {backup}')
    open_position(client, backup, position_side, step_sizes)


def main():
    config = BinanceConfig()
    client = config.get_client()

    print('=== MINA v2 Test Ignition Başlıyor ===')
    ensure_hedge_mode(client)

    step_sizes = get_symbol_filters(client)

    for symbol in LONG_SYMBOLS:
        try_open_with_backup(client, symbol, 'WLDUSDT', 'LONG', step_sizes)

    for symbol in SHORT_SYMBOLS:
        try_open_with_backup(client, symbol, 'XNYUSDT', 'SHORT', step_sizes)

    print('\n--- HEDGE TEST: PARTIUSDT ---')
    try_open_with_backup(client, HEDGE_SYMBOL, 'TONUSDT', 'LONG', step_sizes)
    try_open_with_backup(client, HEDGE_SYMBOL, 'TONUSDT', 'SHORT', step_sizes)

    print('\n--- STRES TESTİ: BTCUSDT LONG ---')
    open_position(client, STRESS_SYMBOL, 'LONG', step_sizes)

    print('\n=== Test Ignition tamamlandı ===')


if __name__ == '__main__':
    main()
