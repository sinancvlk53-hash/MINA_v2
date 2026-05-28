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
    
    exchange_info = client.futures_exchange_info()
    symbol_info = {}
    for s in exchange_info['symbols']:
        precision = 3
        max_qty = float('inf')
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = float(f['stepSize'])
                step_str = str(step).rstrip('0')
                precision = len(step_str.split('.')[-1]) if '.' in step_str else 0
            if f['filterType'] == 'MARKET_LOT_SIZE':
                mq = float(f['maxQty'])
                if mq > 0:
                    max_qty = mq
        symbol_info[s['symbol']] = {'precision': precision, 'max_qty': max_qty}

    for pos in open_positions:
        try:
            symbol = pos['symbol']
            side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
            amount = abs(float(pos['positionAmt']))

            info      = symbol_info.get(symbol, {'precision': 3, 'max_qty': float('inf')})
            precision = info['precision']
            max_qty   = info['max_qty']
            quantity  = round(amount, precision)

            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            pos_side   = 'LONG' if side == 'LONG' else 'SHORT'

            if quantity <= max_qty:
                chunks = [quantity]
            else:
                # -4005: max qty aşıldı — chunk'lara böl
                chunk  = round(max_qty, precision)
                chunks = []
                remaining = quantity
                while remaining > 0:
                    c = round(min(chunk, remaining), precision)
                    if c == 0:
                        break
                    chunks.append(c)
                    remaining = round(remaining - c, precision)
                print(f"   ⚠️  {symbol}: miktar {quantity} > max {max_qty}, {len(chunks)} parçaya bölündü")

            order_ids = []
            for c in chunks:
                order = client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=c,
                    positionSide=pos_side,
                )
                order_ids.append(str(order['orderId']))
                time.sleep(0.2)

            ids_str = ', '.join(order_ids)
            print(f"✅ {symbol} {side} kapatıldı ({len(chunks)} emir) - Order ID: {ids_str}")
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