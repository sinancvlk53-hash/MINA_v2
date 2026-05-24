# -*- coding: utf-8 -*-
"""
Tüm Pozisyonları Kapat
"""

from config import BinanceConfig
from binance.enums import *
import time

def close_all_positions():
    """Tüm açık pozisyonları kapat"""
    print("=" * 70)
    print("🗑️  TÜM POZİSYONLARI KAPATMA")
    print("=" * 70)
    
    config = BinanceConfig()
    client = config.get_client()
    
    # Açık pozisyonları al
    positions = client.futures_position_information()
    open_positions = [p for p in positions if float(p['positionAmt']) != 0]
    
    if len(open_positions) == 0:
        print("📭 Açık pozisyon yok!")
        return
    
    print(f"\n📊 {len(open_positions)} açık pozisyon bulundu:\n")
    
    for pos in open_positions:
        symbol = pos['symbol']
        side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
        amount = abs(float(pos['positionAmt']))
        pnl = float(pos['unRealizedProfit'])
        
        print(f"  - {symbol:12s} {side:5s} | Miktar: {amount:10.4f} | PnL: ${pnl:+.2f}")
    
    # Onay iste
    confirm = input("\n⚠️  HEPSİNİ KAPAT? (EVET yazın): ")
    
    if confirm.upper() != "EVET":
        print("❌ İptal edildi.")
        return
    
    print("\n🚀 Kapatılıyor...\n")
    
    success_count = 0
    failed = []
    
    for pos in open_positions:
        try:
            symbol = pos['symbol']
            side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
            amount = abs(float(pos['positionAmt']))
            
            # Lot size al
            exchange_info = client.futures_exchange_info()
            step_size = 1
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    for f in s['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            break
            
            # Quantity yuvarla
            step_str = str(step_size).rstrip('0')
            precision = len(step_str.split('.')[-1]) if '.' in step_str else 0
            quantity = round(amount, precision)
            
            # Kapat
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide='LONG' if side == 'LONG' else 'SHORT'
            )
            
            print(f"✅ {symbol} {side} kapatıldı - Order ID: {order['orderId']}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ {symbol} {side} hatası: {e}")
            failed.append((symbol, side, str(e)))
        
        time.sleep(0.5)
    
    # Özet
    print("\n" + "=" * 70)
    print("📊 ÖZET")
    print("=" * 70)
    print(f"✅ Kapatılan: {success_count}/{len(open_positions)}")
    
    if failed:
        print(f"❌ Başarısız: {len(failed)}")
        for symbol, side, error in failed:
            print(f"   - {symbol} {side}: {error}")
    
    print("\n✅ İŞLEM TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    close_all_positions()