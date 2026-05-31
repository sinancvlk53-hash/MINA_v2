# -*- coding: utf-8 -*-
"""
MİNA v2 - Defense System
4x kaldıraç için savunma mekanizması
"""

from binance.client import Client
from binance.enums import *
from typing import Dict
import math
import os
import json

_DEFENSE_JSON = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'defense_levels.json')
)

class DefenseSystem:
    """Savunma sistemi - 4x için"""

    def __init__(self, client: Client, slot_size: float):
        self.client = client
        self.slot_size = slot_size

        # Level config (oranlari tum semboller icin paylasimli)
        self.level_config = {
            1: {'trigger_pct': -5.0,  'ratio': 0.20},  # %5 dusus
            2: {'trigger_pct': -10.0, 'ratio': 0.30},  # Likidasyondan %10 once
            3: {'trigger_pct': -10.0, 'ratio': 0.30},  # Likidasyondan %10 once (marjin)
        }

        # Sembol bazli tetikleme durumu: {"DYDXUSDT_SHORT": 1, ...}
        # Deger = tetiklenen en yuksek seviye (0 = hic tetiklenmedi)
        self.triggered_map: Dict[str, int] = self._load_triggered_map()
        print(f"   Defense state restore edildi: {self.triggered_map}")

    def _load_triggered_map(self) -> Dict[str, int]:
        try:
            if os.path.exists(_DEFENSE_JSON):
                with open(_DEFENSE_JSON, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"   defense_levels.json okunamadi: {e}")
        return {}

    def _save_triggered_map(self):
        try:
            with open(_DEFENSE_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.triggered_map, f, indent=2)
        except Exception as e:
            print(f"   Defense state kaydedilemedi: {e}")

    def _is_triggered(self, symbol_key: str, level: int) -> bool:
        return self.triggered_map.get(symbol_key, 0) >= level

    # Eski kod uyumlulugu icin: tek sembol olmadan cagrilabilir
    @property
    def defense_levels(self):
        """Geriye donuk uyumluluk: ilk sembol icin durum dondurir."""
        first_key = next(iter(self.triggered_map), '')
        max_lv = self.triggered_map.get(first_key, 0)
        return {
            1: {**self.level_config[1], 'triggered': max_lv >= 1},
            2: {**self.level_config[2], 'triggered': max_lv >= 2},
            3: {**self.level_config[3], 'triggered': max_lv >= 3},
        }
    
    def calculate_defense_trigger_price(self, entry_price: float, side: str, defense_num: int) -> float:
        """
        Savunma tetik fiyatını hesapla
        Defense 1: LONG → %5 aşağı, SHORT → %5 yukarı
        """
        if defense_num == 1:
            trigger_pct = abs(self.level_config[1]['trigger_pct']) / 100
            if side == 'LONG':
                return entry_price * (1 - trigger_pct)
            else:
                return entry_price * (1 + trigger_pct)
        return 0

    def calculate_liquidation_defense_price(self, liquidation_price: float, entry_price: float) -> float:
        """
        Likidasyondan %10 önceki fiyatı hesapla
        """
        if liquidation_price <= 0:
            return 0
        distance = abs(entry_price - liquidation_price)
        trigger_distance = distance * 0.90

        if entry_price > liquidation_price:  # LONG
            return entry_price - trigger_distance
        else:  # SHORT
            return entry_price + trigger_distance

    def check_defense_trigger(self, position: Dict, current_price: float) -> int:
        """
        Hangi savunmanın tetiklenmesi gerektiğini kontrol et
        Returns: 0 = yok, 1 = defense #1, 2 = defense #2, 3 = defense #3
        """
        symbol_key = f"{position['symbol']}_{position['side']}"
        entry_price = position['entry_price']
        liquidation_price = position['liquidation_price']
        side = position['side']

        # Defense #1: %5 düşüş (LONG) / %5 yükseliş (SHORT)
        defense1_price = self.calculate_defense_trigger_price(entry_price, side, 1)

        if side == 'LONG':
            if current_price <= defense1_price and not self._is_triggered(symbol_key, 1):
                return 1
        else:
            if current_price >= defense1_price and not self._is_triggered(symbol_key, 1):
                return 1

        # Defense #2 ve #3: Likidasyondan %10 önce
        if liquidation_price <= 0:
            return 0
        defense23_price = self.calculate_liquidation_defense_price(liquidation_price, entry_price)

        if side == 'LONG':
            if current_price <= defense23_price:
                if not self._is_triggered(symbol_key, 2):
                    return 2
                elif not self._is_triggered(symbol_key, 3):
                    return 3
        else:
            if current_price >= defense23_price:
                if not self._is_triggered(symbol_key, 2):
                    return 2
                elif not self._is_triggered(symbol_key, 3):
                    return 3

        return 0
    
    def execute_defense(self, position: Dict, defense_num: int, current_price: float) -> bool:
        """
        Savunmayı uygula
        Defense 1 & 2: Pozisyona ekle (BUY/SELL)
        Defense 3: Isolated margin ekle
        """
        symbol = position['symbol']
        side = position['side']
        symbol_key = f"{symbol}_{side}"

        try:
            if defense_num in [1, 2]:
                # Pozisyona ekle
                ratio = self.level_config[defense_num]['ratio']
                defense_amount_usdt = self.slot_size * ratio

                # Quantity hesapla
                quantity = defense_amount_usdt / current_price
                quantity = self._round_quantity(symbol, quantity)

                print(f"\n SAVUNMA #{defense_num} TETIKLENDI!")
                print(f"   Miktar: {quantity} ({defense_amount_usdt} USDT)")
                print(f"   Fiyat: ${current_price}")

                # Emir gönder
                order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL

                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantity,
                    positionSide=side  # Hedge mode uyumlu
                )

                self.triggered_map[symbol_key] = max(self.triggered_map.get(symbol_key, 0), defense_num)
                self._save_triggered_map()
                print(f"   Savunma eklendi! Order ID: {order['orderId']}")
                return True

            elif defense_num == 3:
                # Isolated margin ekle
                ratio = self.level_config[3]['ratio']
                margin_to_add = self.slot_size * ratio

                print(f"\n SAVUNMA #3 TETIKLENDI!")
                print(f"   Marjin Ekleniyor: {margin_to_add} USDT")

                self.client.futures_change_position_margin(
                    symbol=symbol,
                    amount=margin_to_add,
                    type=1  # 1 = Add, 2 = Reduce
                )

                self.triggered_map[symbol_key] = max(self.triggered_map.get(symbol_key, 0), 3)
                self._save_triggered_map()
                print(f"   Marjin eklendi!")
                return True

        except Exception as e:
            print(f"   Savunma hatasi: {e}")
            return False
    
    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Quantity'yi coin'e göre yuvarla"""
        # BTC, ETH gibi coinler için
        if 'BTC' in symbol or 'ETH' in symbol:
            return round(quantity, 5)
        else:
            return round(quantity, 3)
    
    def reset_defenses(self, symbol_key: str = None):
        """Savunma seviyelerini sifirla (yeni pozisyon icin)"""
        if symbol_key:
            self.triggered_map.pop(symbol_key, None)
        else:
            self.triggered_map = {}
        self._save_triggered_map()

    def get_defense_status(self, symbol_key: str = '') -> Dict:
        """Savunma durumunu dondur"""
        max_lv = self.triggered_map.get(symbol_key, 0)
        return {
            'defense_1': max_lv >= 1,
            'defense_2': max_lv >= 2,
            'defense_3': max_lv >= 3,
        }


# =====================================================
# TEST KODU
# =====================================================

if __name__ == "__main__":
    from config import BinanceConfig, AccountManager
    from position_manager import PositionManager
    
    print("🛡️  Defense System Test Başlıyor...\n")
    
    # Bağlan
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    
    # Slot size hesapla
    slot_size = account.calculate_slot_size()
    print(f"📦 Slot Büyüklüğü: {slot_size} USDT\n")
    
    # Defense system oluştur
    defense = DefenseSystem(client, slot_size)
    
    # Test: Bir pozisyon varsa kontrol et
    pm = PositionManager(client)
    positions = pm.get_all_positions()
    
    if positions:
        pos = positions[0]
        print(f"📊 Test Pozisyonu: {pos['symbol']}")
        print(f"   Giriş: ${pos['entry_price']}")
        print(f"   Şuan: ${pos['mark_price']}")
        print(f"   Likvidasyon: ${pos['liquidation_price']}\n")
        
        # Defense tetik fiyatlarını göster
        defense1_price = defense.calculate_defense_trigger_price(pos['entry_price'], pos['side'], 1)
        defense23_price = defense.calculate_liquidation_defense_price(
            pos['liquidation_price'], 
            pos['entry_price']
        )
        
        print(f"🎯 Savunma Tetik Fiyatları:")
        print(f"   Defense #1: ${defense1_price} (%5 düşüş)")
        print(f"   Defense #2&3: ${defense23_price} (likidasyon %10 önce)")
        
        # Kontrol et
        defense_trigger = defense.check_defense_trigger(pos, pos['mark_price'])
        if defense_trigger > 0:
            print(f"\n⚠️  Savunma #{defense_trigger} tetiklenmeli!")
        else:
            print(f"\n✅ Henüz savunma tetiklenmedi")
    else:
        print("ℹ️  Açık pozisyon yok, test edilemedi.")
        print("   Önce bir pozisyon açın!")
    
    print("\n✅ Test tamamlandı!")