# -*- coding: utf-8 -*-
"""
MİNA v2 - Strategy Manager
Tüm kaldıraçlar için strateji yöneticisi
"""

from binance.client import Client
from binance.enums import *
from typing import Dict, Optional
from defense_system import DefenseSystem

class StrategyManager:
    """Kaldıraç bazlı strateji yöneticisi"""
    
    def __init__(self, client: Client, slot_size: float):
        self.client = client
        self.slot_size = slot_size
        
        # 4x için defense system
        self.defense_system = DefenseSystem(client, slot_size)
        
        # Kaldıraç kuralları
        self.leverage_rules = {
            1: {'has_defense': False, 'stop_loss_pct': 3.0, 'tp_type': 'standard'},
            2: {'has_defense': False, 'stop_loss_pct': 3.0, 'tp_type': 'standard'},
            3: {'has_defense': False, 'stop_loss_pct': 3.0, 'tp_type': 'standard'},
            4: {'has_defense': True, 'stop_loss_pct': None, 'tp_type': 'standard'},
            5: {'has_defense': False, 'stop_loss_pct': 2.0, 'tp_type': 'standard'},
            10: {'has_defense': False, 'stop_loss_pct': 1.0, 'tp_type': 'fast'}
        }
        
        # Kar alma kuralları
        self.tp_rules = {
            'standard': {
                'tp1_pct': 3.0,      # %3 → %50 sat
                'tp2_pct': 5.0,      # %5 → %25 daha sat
                'trailing_pct': 1.0  # %1 trailing
            },
            'fast': {
                'tp1_pct': 2.0,      # %2 → %50 sat (10x için)
                'tp2_pct': 4.0,      # %4 → %25 daha sat
                'trailing_pct': 1.0  # %1 trailing
            }
        }
    
    def check_position_action(self, position: Dict, current_price: float) -> Dict:
        """
        Pozisyon için gerekli aksiyonu kontrol et
        Returns: {
            'action': 'defense' / 'stop_loss' / 'take_profit' / 'trailing_stop' / 'hold',
            'level': 1/2/3 (defense veya tp için),
            'reason': 'açıklama'
        }
        """
        leverage = position['leverage']
        entry_price = position['entry_price']
        side = position['side']
        
        # PnL yüzdesini hesapla
        if side == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        rules = self.leverage_rules.get(leverage)
        if not rules:
            return {'action': 'hold', 'reason': f'Bilinmeyen kaldıraç: {leverage}x'}
        
        # 4x için savunma kontrolü
        if rules['has_defense']:
            defense_trigger = self.defense_system.check_defense_trigger(position, current_price)
            if defense_trigger > 0:
                return {
                    'action': 'defense',
                    'level': defense_trigger,
                    'reason': f'Savunma #{defense_trigger} tetiklendi'
                }
        
        # Diğer kaldıraçlar için stop-loss kontrolü
        else:
            stop_loss_pct = rules['stop_loss_pct']
            if pnl_pct <= -stop_loss_pct:
                return {
                    'action': 'stop_loss',
                    'pnl': pnl_pct,
                    'reason': f'Stop-loss tetiklendi: %{pnl_pct:.2f} (limit: %{-stop_loss_pct})'
                }
        
        # Kar alma kontrolü (tüm kaldıraçlar için)
        tp_type = rules['tp_type']
        tp_rule = self.tp_rules[tp_type]
        
        tp_done = position.get('tp_level', 0)

        # TP2 önce kontrol et — TP1 zaten tamamlanmışsa
        if tp_done >= 1 and pnl_pct >= tp_rule['tp2_pct']:
            return {
                'action': 'take_profit',
                'level': 2,
                'pnl': pnl_pct,
                'reason': f'TP2 tetiklendi: %{pnl_pct:.2f} (hedef: %{tp_rule["tp2_pct"]})'
            }

        # TP1 — henüz tetiklenmemişse
        if tp_done == 0 and pnl_pct >= tp_rule['tp1_pct']:
            return {
                'action': 'take_profit',
                'level': 1,
                'pnl': pnl_pct,
                'reason': f'TP1 tetiklendi: %{pnl_pct:.2f} (hedef: %{tp_rule["tp1_pct"]})'
            }
        
        # Trailing stop kontrolü
        # TODO: En yüksek fiyatı kaydet ve %1 düşüşü kontrol et
        
        return {'action': 'hold', 'reason': 'Normal izleme'}
    
    def execute_action(self, position: Dict, action: Dict, current_price: float) -> bool:
        """Aksiyonu uygula"""
        action_type = action['action']
        
        try:
            if action_type == 'defense':
                # 4x savunma sistemi
                return self.defense_system.execute_defense(
                    position, 
                    action['level'], 
                    current_price
                )
            
            elif action_type == 'stop_loss':
                # Stop-loss: Tüm pozisyonu kapat
                return self._close_position(position, 'STOP_LOSS')
            
            elif action_type == 'take_profit':
                # Kar alma: Belirtilen miktarı sat
                level = action['level']
                if level == 1:
                    return self._partial_close(position, 0.50, 'TP1')  # %50
                elif level == 2:
                    return self._partial_close(position, 0.50, 'TP2')  # Kalan'ın %50'si
            
            elif action_type == 'trailing_stop':
                # Trailing stop: Kalan tümünü kapat
                return self._close_position(position, 'TRAILING_STOP')
            
            return False
            
        except Exception as e:
            print(f"❌ Aksiyon hatası: {e}")
            return False
    
    def _close_position(self, position: Dict, reason: str) -> bool:
        """Pozisyonu tamamen kapat"""
        symbol = position['symbol']
        amount = position['amount']
        side = position['side']
        
        print(f"\n🚪 POZİSYON KAPATILIYOR: {reason}")
        print(f"   {symbol} - {side}")
        print(f"   Miktar: {amount}")
        
        try:
            # Ters emir gönder
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=amount,
                positionSide=side
            )
            
            print(f"   ✅ Pozisyon kapatıldı! Order ID: {order['orderId']}")
            return True
            
        except Exception as e:
            print(f"   ❌ Kapatma hatası: {e}")
            return False
    
    def _partial_close(self, position: Dict, ratio: float, reason: str) -> bool:
        """Pozisyonun bir kısmını kapat"""
        symbol = position['symbol']
        amount = position['amount']
        side = position['side']
        
        close_amount = amount * ratio
        close_amount = round(close_amount, 5)
        
        print(f"\n💰 KISMİ KAPAMA: {reason}")
        print(f"   {symbol} - {side}")
        print(f"   Kapatılacak: {close_amount} (Toplam'ın %{ratio*100})")
        
        try:
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=close_amount,
                positionSide=side
            )
            
            print(f"   ✅ Kısmi kapatma başarılı! Order ID: {order['orderId']}")
            return True
            
        except Exception as e:
            print(f"   ❌ Kısmi kapatma hatası: {e}")
            return False
    
    def get_rules_for_leverage(self, leverage: int) -> Dict:
        """Belirtilen kaldıraç için kuralları döndür"""
        return self.leverage_rules.get(leverage, {})


# =====================================================
# TEST KODU
# =====================================================

if __name__ == "__main__":
    from config import BinanceConfig, AccountManager
    from position_manager import PositionManager
    
    print("🎯 Strategy Manager Test Başlıyor...\n")
    
    # Bağlan
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    
    # Slot size
    slot_size = account.calculate_slot_size()
    
    # Strategy manager oluştur
    strategy = StrategyManager(client, slot_size)
    
    # Kaldıraç kurallarını göster
    print("📋 KALDIRAC KURALLARI:")
    print("=" * 60)
    for lev, rules in strategy.leverage_rules.items():
        print(f"{lev}x: Savunma={rules['has_defense']}, Stop={rules['stop_loss_pct']}%, TP={rules['tp_type']}")
    
    print("\n✅ Test tamamlandı!")