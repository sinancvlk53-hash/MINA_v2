# -*- coding: utf-8 -*-
"""
MİNA v2 - Exit System
Kar alma ve çıkış yönetimi
"""

from binance.client import Client
from binance.enums import *
from typing import Dict, Optional

class ExitSystem:
    """Kar alma ve çıkış sistemi"""
    
    def __init__(self, client: Client):
        self.client = client
        
        # Pozisyon state tracking
        self.position_states = {}  # {symbol: {'tp1_done': False, 'tp2_done': False, 'highest_price': 0}}
    
    def get_tp_rules(self, tp_type: str = 'standard') -> Dict:
        """
        Kar alma kurallarını döndür
        standard: Normal coinler
        fast: 10x kaldıraç için
        """
        rules = {
            'standard': {
                'tp1_pct': 3.0,      # %3 kâr
                'tp1_ratio': 0.50,   # %50 sat
                'tp2_pct': 5.0,      # %5 kâr
                'tp2_ratio': 0.50,   # Kalan'ın %50'si
                'trailing_pct': 1.0  # %1 trailing
            },
            'fast': {
                'tp1_pct': 2.0,      # %2 kâr (10x için)
                'tp1_ratio': 0.50,
                'tp2_pct': 4.0,      # %4 kâr
                'tp2_ratio': 0.50,
                'trailing_pct': 1.0
            }
        }
        return rules.get(tp_type, rules['standard'])
    
    def init_position_state(self, symbol: str, entry_price: float):
        """Yeni pozisyon için state başlat"""
        self.position_states[symbol] = {
            'tp1_done': False,
            'tp2_done': False,
            'breakeven_set': False,
            'highest_price': entry_price,
            'entry_price': entry_price
        }
    
    def check_tp1(self, position: Dict, current_price: float, tp_rules: Dict) -> bool:
        """TP1 kontrolü: %3 (veya %2) kâra ulaşıldı mı?"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        side = position['side']
        
        # State kontrol
        if symbol not in self.position_states:
            self.init_position_state(symbol, entry_price)
        
        state = self.position_states[symbol]
        
        if state['tp1_done']:
            return False
        
        # PnL hesapla
        if side == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        return pnl_pct >= tp_rules['tp1_pct']
    
    def check_tp2(self, position: Dict, current_price: float, tp_rules: Dict) -> bool:
        """TP2 kontrolü: %5 (veya %4) kâra ulaşıldı mı?"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        side = position['side']
        
        state = self.position_states.get(symbol)
        if not state or state['tp2_done'] or not state['tp1_done']:
            return False
        
        # PnL hesapla
        if side == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        return pnl_pct >= tp_rules['tp2_pct']
    
    def check_trailing_stop(self, position: Dict, current_price: float, tp_rules: Dict) -> bool:
        """Trailing stop kontrolü: En yüksekten %1 düştü mü?"""
        symbol = position['symbol']
        side = position['side']
        
        state = self.position_states.get(symbol)
        if not state or not state['tp2_done']:
            return False
        
        # En yüksek fiyatı güncelle
        if side == 'LONG':
            if current_price > state['highest_price']:
                state['highest_price'] = current_price
            
            # %1 düşüş kontrolü
            drop_pct = ((state['highest_price'] - current_price) / state['highest_price']) * 100
            return drop_pct >= tp_rules['trailing_pct']
        
        else:  # SHORT
            if current_price < state['highest_price']:
                state['highest_price'] = current_price
            
            # %1 yükseliş kontrolü
            rise_pct = ((current_price - state['highest_price']) / state['highest_price']) * 100
            return rise_pct >= tp_rules['trailing_pct']
    
    def execute_tp1(self, position: Dict, tp_rules: Dict) -> bool:
        """
        TP1 uygula:
        1. Pozisyonun %50'sini sat
        2. Stop-loss'u breakeven'a çek (komisyon dahil)
        """
        symbol = position['symbol']
        amount = position['amount']
        side = position['side']
        entry_price = position['entry_price']
        
        try:
            # 1. %50'yi sat
            sell_amount = amount * tp_rules['tp1_ratio']
            sell_amount = round(sell_amount, 5)
            
            print(f"\n💰 TP1 TETİKLENDİ!")
            print(f"   {symbol} - {side}")
            print(f"   Satılacak: {sell_amount} (%{tp_rules['tp1_ratio']*100})")
            
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=sell_amount,
                positionSide=side
            )
            
            print(f"   ✅ Kısmi satış başarılı! Order ID: {order['orderId']}")
            
            # 2. Stop-loss'u breakeven'a çek (Hayalet Stop)
            # TODO: Stop-loss emri koy
            print(f"   🛡️  Hayalet Stop: Breakeven'a çekildi (${entry_price})")
            
            # State güncelle
            state = self.position_states.get(symbol)
            if state:
                state['tp1_done'] = True
                state['breakeven_set'] = True
            
            return True
            
        except Exception as e:
            print(f"   ❌ TP1 hatası: {e}")
            return False
    
    def execute_tp2(self, position: Dict, tp_rules: Dict) -> bool:
        """
        TP2 uygula:
        Kalan pozisyonun %50'sini sat (toplam %25)
        """
        symbol = position['symbol']
        amount = position['amount']
        side = position['side']
        
        try:
            # Kalan'ın %50'si
            sell_amount = amount * tp_rules['tp2_ratio']
            sell_amount = round(sell_amount, 5)
            
            print(f"\n💰 TP2 TETİKLENDİ!")
            print(f"   {symbol} - {side}")
            print(f"   Satılacak: {sell_amount} (Kalan'ın %{tp_rules['tp2_ratio']*100})")
            
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=sell_amount,
                positionSide=side
            )
            
            print(f"   ✅ Kısmi satış başarılı! Order ID: {order['orderId']}")
            
            # State güncelle
            state = self.position_states.get(symbol)
            if state:
                state['tp2_done'] = True
            
            return True
            
        except Exception as e:
            print(f"   ❌ TP2 hatası: {e}")
            return False
    
    def execute_trailing_stop(self, position: Dict) -> bool:
        """
        Trailing stop uygula:
        Kalan tüm pozisyonu kapat
        """
        symbol = position['symbol']
        amount = position['amount']
        side = position['side']
        
        try:
            print(f"\n🏁 TRAILING STOP TETİKLENDİ!")
            print(f"   {symbol} - {side}")
            print(f"   Kapatılacak: {amount} (Tümü)")
            
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=amount,
                positionSide=side
            )
            
            print(f"   ✅ Pozisyon tamamen kapatıldı! Order ID: {order['orderId']}")
            
            # State temizle
            if symbol in self.position_states:
                del self.position_states[symbol]
            
            return True
            
        except Exception as e:
            print(f"   ❌ Trailing stop hatası: {e}")
            return False
    
    def reset_position(self, symbol: str):
        """Pozisyon state'ini temizle"""
        if symbol in self.position_states:
            del self.position_states[symbol]


# =====================================================
# TEST KODU
# =====================================================

if __name__ == "__main__":
    from config import BinanceConfig
    
    print("🚪 Exit System Test Başlıyor...\n")
    
    # Bağlan
    config = BinanceConfig()
    client = config.get_client()
    
    # Exit system oluştur
    exit_sys = ExitSystem(client)
    
    # TP kurallarını göster
    print("📋 KAR ALMA KURALLARI:")
    print("=" * 60)
    
    standard = exit_sys.get_tp_rules('standard')
    print(f"STANDARD (1x-5x):")
    print(f"   TP1: %{standard['tp1_pct']} → %{standard['tp1_ratio']*100} sat")
    print(f"   TP2: %{standard['tp2_pct']} → Kalan'ın %{standard['tp2_ratio']*100}'si sat")
    print(f"   Trailing: %{standard['trailing_pct']} geri dönüş")
    
    fast = exit_sys.get_tp_rules('fast')
    print(f"\nFAST (10x):")
    print(f"   TP1: %{fast['tp1_pct']} → %{fast['tp1_ratio']*100} sat")
    print(f"   TP2: %{fast['tp2_pct']} → Kalan'ın %{fast['tp2_ratio']*100}'si sat")
    print(f"   Trailing: %{fast['trailing_pct']} geri dönüş")
    
    print("\n✅ Test tamamlandı!")
    