# -*- coding: utf-8 -*-
"""
MİNA v2 - Position Manager
Açık pozisyonları takip et ve yönet
"""

from binance.client import Client
from typing import List, Dict
import time

class PositionManager:
    """Pozisyon takip ve yönetim sistemi"""
    
    def __init__(self, client: Client):
        self.client = client
        self.slot_count = 10
    
    def parse_open_positions(self, raw_positions: List[Dict]) -> List[Dict]:
        """Tek futures_position_information çağrısından pozisyon listesi."""
        open_positions = []
        for pos in raw_positions:
            amount = float(pos['positionAmt'])
            if amount == 0:
                continue
            lev = 0
            try:
                lev = int(pos.get('leverage') or 0)
            except (TypeError, ValueError):
                lev = 0
            if lev <= 0:
                lev = 4
            iso = float(pos.get('isolatedMargin') or pos.get('isolatedWallet') or 0)
            open_positions.append({
                'symbol': pos['symbol'],
                'side': 'LONG' if amount > 0 else 'SHORT',
                'amount': abs(amount),
                'entry_price': float(pos['entryPrice']),
                'mark_price': float(pos['markPrice']),
                'liquidation_price': float(pos['liquidationPrice']),
                'unrealized_pnl': float(pos['unRealizedProfit']),
                'leverage': lev,
                'margin_type': pos.get('marginType', 'isolated'),
                'isolated_margin': iso,
            })
        return open_positions

    def get_all_positions(self) -> List[Dict]:
        """
        Tüm açık pozisyonları getir
        Returns: [{'symbol': 'BTCUSDT', 'amount': 0.001, 'entry': 77000, ...}]
        """
        try:
            positions = self.client.futures_position_information()
            return self.parse_open_positions(positions)
            
        except Exception as e:
            print(f"❌ Pozisyon okuma hatası: {e}")
            return []
    
    def get_position_by_symbol(self, symbol: str) -> Dict:
        """Belirli bir coin'in pozisyonunu getir"""
        positions = self.get_all_positions()
        for pos in positions:
            if pos['symbol'] == symbol:
                return pos
        return None
    
    def calculate_pnl_percent(self, position: Dict) -> float:
        """Pozisyon için PnL yüzdesini hesapla"""
        entry = position['entry_price']
        current = position['mark_price']
        side = position['side']
        
        if side == 'LONG':
            pnl_pct = ((current - entry) / entry) * 100
        else:
            pnl_pct = ((entry - current) / entry) * 100
        
        return round(pnl_pct, 2)
    
    def get_used_margin(self) -> float:
        """Toplam kullanılan marjini hesapla"""
        account = self.client.futures_account()
        return float(account['totalMarginBalance'])
    
    def get_available_balance(self) -> float:
        """Kullanılabilir bakiyeyi getir"""
        account = self.client.futures_account()
        return float(account['availableBalance'])
    
    def calculate_slot_usage(self, total_balance: float) -> Dict:
        """
        Slot kullanımını hesapla
        Returns: {
            'slot_size': 448.74,
            'used_slots': 2.5,
            'free_slots': 7.5,
            'can_open_new': True
        }
        """
        slot_size = total_balance / self.slot_count
        positions = self.get_all_positions()
        
        # Her pozisyonun kaç slot kullandığını hesapla
        total_used_slots = 0
        for pos in positions:
            # Isolated margin = bu pozisyon için kullanılan para
            margin_used = pos['isolated_margin']
            slots_used = margin_used / slot_size
            total_used_slots += slots_used
        
        free_slots = self.slot_count - total_used_slots
        
        return {
            'total_balance': round(total_balance, 2),
            'slot_size': round(slot_size, 2),
            'used_slots': round(total_used_slots, 2),
            'free_slots': round(free_slots, 2),
            'active_positions': len(positions),
            'can_open_new': free_slots >= 1.0  # En az 1 slot boş olmalı
        }
    
    def print_positions_summary(self):
        """Pozisyonların özetini ekrana bas"""
        print("\n" + "=" * 80)
        print("📊 AÇIK POZİSYONLAR")
        print("=" * 80)
        
        positions = self.get_all_positions()
        
        if not positions:
            print("\n✅ Hiç açık pozisyon yok!")
            return
        
        for i, pos in enumerate(positions, 1):
            pnl_pct = self.calculate_pnl_percent(pos)
            emoji = "📈" if pnl_pct > 0 else "📉"
            
            print(f"\n{i}. {pos['symbol']} - {pos['side']}")
            print(f"   💰 Miktar: {pos['amount']}")
            print(f"   📍 Giriş: ${pos['entry_price']}")
            print(f"   📍 Şuan: ${pos['mark_price']}")
            print(f"   {emoji} PnL: {pnl_pct}% (${pos['unrealized_pnl']})")
            print(f"   ⚡ Kaldıraç: {pos['leverage']}x")
            print(f"   🔴 Likvidasyon: ${pos['liquidation_price']}")
            print(f"   💵 Marjin: ${pos['isolated_margin']}")
        
        # Slot özeti
        account = self.client.futures_account_balance()
        total_balance = 0
        for asset in account:
            if asset['asset'] == 'USDT':
                total_balance = float(asset['balance'])
        
        slot_info = self.calculate_slot_usage(total_balance)
        
        print("\n" + "-" * 80)
        print("🎰 SLOT DURUMU")
        print("-" * 80)
        print(f"💰 Toplam Bakiye: {slot_info['total_balance']} USDT")
        print(f"📦 Slot Büyüklüğü: {slot_info['slot_size']} USDT")
        print(f"🔴 Kullanılan Slot: {slot_info['used_slots']} / 10")
        print(f"🟢 Boş Slot: {slot_info['free_slots']} / 10")
        print(f"{'✅' if slot_info['can_open_new'] else '❌'} Yeni Pozisyon: {'Açılabilir' if slot_info['can_open_new'] else 'DOLU!'}")
        print("=" * 80)


# =====================================================
# TEST KODU
# =====================================================

if __name__ == "__main__":
    from config import BinanceConfig
    
    print("🔍 Position Manager Test Başlıyor...\n")
    
    # Bağlan
    config = BinanceConfig()
    client = config.get_client()
    
    # Position Manager oluştur
    pm = PositionManager(client)
    
    # Özeti göster
    pm.print_positions_summary()
    
    print("\n✅ Test tamamlandı!")