# -*- coding: utf-8 -*-
"""
10 Pozisyon Toplu Açma
"""

from config import BinanceConfig, AccountManager
from binance.enums import *
import time

# ═══════════════════════════════════════════════
# 10 POZİSYON LİSTESİ
# ═══════════════════════════════════════════════

POSITIONS = [
    {"symbol": "AGTUSDT",   "side": "LONG",  "leverage": 4},
    {"symbol": "AGTUSDT",   "side": "SHORT", "leverage": 4},
    {"symbol": "UBUSDT",    "side": "LONG",  "leverage": 4},
    {"symbol": "UBUSDT",    "side": "SHORT", "leverage": 4},
    {"symbol": "PLUMEUSDT", "side": "LONG",  "leverage": 4},
    {"symbol": "PLUMEUSDT", "side": "SHORT", "leverage": 4},
    {"symbol": "BASUSDT",   "side": "LONG",  "leverage": 4},
    {"symbol": "BASUSDT",   "side": "SHORT", "leverage": 4},
    {"symbol": "DEXEUSDT",  "side": "LONG",  "leverage": 4},
    {"symbol": "AKTUSDT",   "side": "SHORT", "leverage": 4}
]

# ═══════════════════════════════════════════════

def open_position(client, account, symbol, side, leverage):
    """Tek pozisyon aç"""
    try:
        # Otomatik slot hesaplama
        balance = account.get_usdt_balance()
        slot_size = balance / 10
        amount_usdt = slot_size * 0.20
        
        print(f"\n{'='*60}")
        print(f"📊 {symbol} - {side} {leverage}x")
        print(f"{'='*60}")
        
        # Kaldıraç
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"✅ Kaldıraç: {leverage}x")
        except Exception as e:
            print(f"⚠️  Kaldıraç: {e}")
        
        # Margin type
        try:
            client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
            print(f"✅ Margin: ISOLATED")
        except:
            print(f"✅ Margin: Zaten ISOLATED")
        
        # Lot size
        exchange_info = client.futures_exchange_info()
        step_size = 1
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        break
        
        # Fiyat
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        
        # Quantity
        position_size = amount_usdt * leverage
        raw_qty = position_size / price
        step_str = str(step_size).rstrip('0')
        precision = len(step_str.split('.')[-1]) if '.' in step_str else 0
        quantity = round(raw_qty, precision)
        
        print(f"💰 Bakiye: {balance:.2f} USDT")
        print(f"📦 Slot: {slot_size:.2f} USDT")
        print(f"💵 Margin: {amount_usdt:.2f} USDT")
        print(f"💵 Fiyat: ${price:.4f}")
        print(f"📦 Miktar: {quantity}")
        
        # Pozisyon aç
        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )
        
        print(f"✅ AÇILDI! Order ID: {order['orderId']}")
        
        return True, None
        
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 70)
    print("🚀 10 POZİSYON AÇMA")
    print("=" * 70)
    print(f"📊 Toplam: {len(POSITIONS)} pozisyon")
    print("=" * 70)
    
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    
    # Onay
    print(f"\n📋 Pozisyon Listesi:")
    for i, pos in enumerate(POSITIONS, 1):
        print(f"{i:2d}. {pos['symbol']:12s} - {pos['side']:5s} {pos['leverage']}x")
    
    confirm = input("\nDevam? (EVET yazın): ")
    
    if confirm.upper() != "EVET":
        print("❌ İptal.")
        return
    
    print("\n🚀 Başlıyor...\n")
    
    success_count = 0
    failed = []
    
    for i, pos in enumerate(POSITIONS, 1):
        print(f"\n[{i}/{len(POSITIONS)}]")
        
        success, error = open_position(
            client, account, 
            pos['symbol'], 
            pos['side'], 
            pos['leverage']
        )
        
        if success:
            success_count += 1
        else:
            failed.append((pos['symbol'], pos['side'], error))
            print(f"❌ HATA: {error}")
        
        time.sleep(1)
    
    # Özet
    print("\n" + "=" * 70)
    print("📊 ÖZET")
    print("=" * 70)
    print(f"✅ Başarılı: {success_count}/{len(POSITIONS)}")
    
    if failed:
        print(f"❌ Başarısız: {len(failed)}")
        for symbol, side, error in failed:
            print(f"   - {symbol} {side}: {error}")
    
    print("\n✅ İŞLEM TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    main()