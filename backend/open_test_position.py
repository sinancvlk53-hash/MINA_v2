# -*- coding: utf-8 -*-
"""Test pozisyonu aç"""

from config import BinanceConfig, AccountManager
from binance.enums import *

config = BinanceConfig()
client = config.get_client()
account = AccountManager(client)

symbol = "SOLUSDT"
leverage = 4

# ═══════════════════════════════════════════════
# OTOMATİK SLOT HESAPLAMA (MİNA v2 Sistemi)
# ═══════════════════════════════════════════════
balance = account.get_usdt_balance()  # Toplam bakiye
slot_size = balance / 10              # Slot = Bakiye ÷ 10
amount_usdt = slot_size * 0.20        # Margin = Slot × %20

print(f"🚀 Test Pozisyonu Açılıyor...")
print(f"   Coin: {symbol}")
print(f"   Kaldıraç: {leverage}x")
print(f"💰 Bakiye: {balance} USDT")
print(f"🎰 Slot Büyüklüğü: {slot_size} USDT")
print(f"📥 Margin (İlk Giriş): {amount_usdt} USDT")
print(f"📊 Pozisyon Büyüklüğü: {amount_usdt * leverage} USDT\n")

# Kaldıraç ayarla
try:
    client.futures_change_leverage(symbol=symbol, leverage=leverage)
except:
    pass

# Lot size bilgisini Binance'den al
exchange_info = client.futures_exchange_info()
step_size = 1
for s in exchange_info['symbols']:
    if s['symbol'] == symbol:
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                break

# Fiyat al
ticker = client.futures_symbol_ticker(symbol=symbol)
price = float(ticker['price'])

# Miktarı hesapla (KALDIRAÇLA!)
position_size = amount_usdt * leverage  # Margin × Kaldıraç = Toplam pozisyon
raw_qty = position_size / price
precision = len(str(step_size).rstrip('0').split('.')[-1])
quantity = round(raw_qty, precision)

print(f"💵 Fiyat: ${price}")
print(f"📦 Miktar: {quantity} SOL\n")

# Pozisyon aç
order = client.futures_create_order(
    symbol=symbol,
    side=SIDE_BUY,
    type=ORDER_TYPE_MARKET,
    quantity=quantity,
    positionSide='LONG'
)

print(f"✅ POZİSYON AÇILDI!")
print(f"Order ID: {order['orderId']}")
print(f"Kullanılan Margin: ~{amount_usdt} USDT")
print(f"Pozisyon Değeri: ~{amount_usdt * leverage} USDT\n")