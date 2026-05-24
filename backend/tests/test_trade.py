# -*- coding: utf-8 -*-
"""
MİNA v2 - Test Trade
Testnet'te küçük bir işlem yapıp test edelim
"""

from config import BinanceConfig, AccountManager
from binance.enums import *

def test_market_order():
    """Basit bir market emri test et"""
    
    print("=" * 60)
    print("🧪 MİNA v2 - TEST TRADE BAŞLIYOR")
    print("=" * 60)
    
    # Bağlantı kur
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    
    # Bakiye kontrol
    balance = account.get_usdt_balance()
    print(f"\n💰 Mevcut Bakiye: {balance} USDT")
    
    # Test parametreleri
    symbol = "BTCUSDT"
    leverage = 4
    test_amount = 100  # 100 USDT'lik test
    
    print(f"\n📊 Test Parametreleri:")
    print(f"   Coin: {symbol}")
    print(f"   Kaldıraç: {leverage}x")
    print(f"   Miktar: {test_amount} USDT")
    
    try:
        # 0. Position Mode'u tespit et (değiştirme, sadece öğren)
        print(f"\n0️⃣ Position Mode tespit ediliyor...")
        position_mode_info = client.futures_get_position_mode()
        dual_side_position = position_mode_info['dualSidePosition']
        
        if dual_side_position:
            print(f"   📌 Position Mode: HEDGE MODE (Çift Yönlü)")
            print(f"   ℹ️  positionSide parametresi kullanılacak")
            use_position_side = True
        else:
            print(f"   📌 Position Mode: ONE-WAY MODE (Tek Yönlü)")
            print(f"   ℹ️  positionSide parametresi kullanılmayacak")
            use_position_side = False
        
        # 1. Kaldıracı ayarla
        print(f"\n1️⃣ Kaldıraç {leverage}x olarak ayarlanıyor...")
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"   ✅ Kaldıraç ayarlandı: {leverage}x")
        except Exception as e:
            if 'No need to change' in str(e) or 'leverage not modified' in str(e).lower():
                print(f"   ✅ Kaldıraç zaten {leverage}x")
            else:
                raise
        
        # 2. Margin tipini ISOLATED yap
        print(f"\n2️⃣ Margin tipi ISOLATED yapılıyor...")
        try:
            client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
            print(f"   ✅ Margin tipi: ISOLATED")
        except Exception as e:
            if 'No need to change' in str(e):
                print(f"   ✅ Margin tipi zaten ISOLATED")
            else:
                raise
        
        # 3. Güncel fiyatı al
        print(f"\n3️⃣ Güncel fiyat alınıyor...")
        ticker = client.futures_symbol_ticker(symbol=symbol)
        current_price = float(ticker['price'])
        print(f"   💵 Güncel {symbol} Fiyatı: ${current_price}")
        
        # 4. Quantity hesapla (BTC cinsinden)
        quantity = test_amount / current_price
        quantity = round(quantity, 5)  # BTC için 5 ondalık
        print(f"   📦 Alınacak Miktar: {quantity} BTC")
        
        # 5. LONG pozisyon aç (Mode'a göre)
        print(f"\n4️⃣ LONG pozisyon açılıyor...")
        
        order_params = {
            'symbol': symbol,
            'side': SIDE_BUY,
            'type': ORDER_TYPE_MARKET,
            'quantity': quantity
        }
        
        # Eğer Hedge Mode ise positionSide ekle
        if use_position_side:
            order_params['positionSide'] = 'LONG'
        
        order = client.futures_create_order(**order_params)
        print(f"   ✅ Pozisyon Açıldı!")
        print(f"   📝 Order ID: {order['orderId']}")
        
        # 6. Pozisyon bilgisini al
        print(f"\n5️⃣ Pozisyon kontrol ediliyor...")
        positions = client.futures_position_information(symbol=symbol)
        for pos in positions:
            if float(pos['positionAmt']) != 0:
                print(f"   📊 Açık Pozisyon:")
                print(f"      Miktar: {pos['positionAmt']} BTC")
                print(f"      Giriş Fiyatı: ${pos['entryPrice']}")
                print(f"      PnL: ${pos['unRealizedProfit']}")
                if use_position_side:
                    print(f"      Pozisyon Tarafı: {pos.get('positionSide', 'N/A')}")
        
        # 7. Pozisyonu kapat (Mode'a göre)
        print(f"\n6️⃣ Pozisyon kapatılıyor...")
        
        close_params = {
            'symbol': symbol,
            'side': SIDE_SELL,
            'type': ORDER_TYPE_MARKET,
            'quantity': quantity
        }
        
        # Eğer Hedge Mode ise positionSide ekle
        if use_position_side:
            close_params['positionSide'] = 'LONG'
        
        close_order = client.futures_create_order(**close_params)
        print(f"   ✅ Pozisyon Kapatıldı!")
        print(f"   📝 Close Order ID: {close_order['orderId']}")
        
        # 8. Yeni bakiye
        print(f"\n7️⃣ Yeni bakiye kontrol ediliyor...")
        new_balance = account.get_usdt_balance()
        profit_loss = new_balance - balance
        print(f"   💰 Yeni Bakiye: {new_balance} USDT")
        print(f"   {'📈' if profit_loss >= 0 else '📉'} Fark: {profit_loss:.4f} USDT")
        
        print("\n" + "=" * 60)
        print("✅ TEST TRADE BAŞARILI!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        print("\nHata Detayı:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Kullanıcıdan onay al
    print("\n⚠️  DİKKAT: Bu script Binance Testnet'te küçük bir işlem yapacak.")
    onay = input("Devam etmek istiyor musunuz? (evet/hayir): ")
    
    if onay.lower() in ['evet', 'e', 'yes', 'y']:
        test_market_order()
    else:
        print("❌ İşlem iptal edildi.")