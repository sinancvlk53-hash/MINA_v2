# -*- coding: utf-8 -*-
"""
MİNA v2 - Ana Trading Bot
Tüm sistemleri birleştiren ana motor
"""

import sys
import time
import json
from datetime import datetime
from binance.client import Client
from binance.streams import ThreadedWebsocketManager
from typing import Dict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from config import BinanceConfig, AccountManager
from position_manager import PositionManager
from strategy_manager import StrategyManager
from exit_system import ExitSystem

class TradingBot:
    """Ana trading bot motoru"""
    
    def __init__(self):
        print("=" * 70)
        print("🤖 MİNA v2 TRADING BOT BAŞLATILIYOR...")
        print("=" * 70)
        
        # Binance bağlantısı
        self.config = BinanceConfig()
        self.client = self.config.get_client()
        print("✅ Binance bağlantısı kuruldu")
        
        # Modüller
        self.account = AccountManager(self.client)
        self.position_manager = PositionManager(self.client)
        
        slot_size = self.account.calculate_slot_size()
        self.strategy_manager = StrategyManager(self.client, slot_size)
        self.exit_system = ExitSystem(self.client)
        
        print(f"✅ Slot büyüklüğü: {slot_size} USDT")
        
        # WebSocket manager
        self.twm = None
        self.active_streams = {}  # {symbol: stream_key}
        
        # Ana döngü kontrolü
        self.running = False
        
        print("✅ Tüm modüller yüklendi")
        print("=" * 70 + "\n")
    
    def start_price_stream(self, symbol: str):
        """Bir coin için fiyat stream'i başlat"""
        if symbol in self.active_streams:
            return  # Zaten dinleniyor
        
        if not self.twm:
            self.twm = ThreadedWebsocketManager(
                api_key=self.config.api_key,
                api_secret=self.config.api_secret,
                testnet=self.config.testnet
            )
            self.twm.start()
        
        # Stream başlat
        stream_key = self.twm.start_symbol_mark_price_socket(
            callback=self._price_callback,
            symbol=symbol.lower()
        )
        
        self.active_streams[symbol] = stream_key
        print(f"📡 {symbol} fiyat stream'i başlatıldı")
    
    def _price_callback(self, msg):
        """WebSocket'ten gelen fiyat güncellemeleri"""
        if msg['e'] == 'markPriceUpdate':
            symbol = msg['s']
            price = float(msg['p'])
            
            # Bu coin için açık pozisyon var mı?
            position = self.position_manager.get_position_by_symbol(symbol)
            
            if position:
                self._check_position_actions(position, price)
    
    def _check_position_actions(self, position: Dict, current_price: float):
        """Pozisyon için gerekli aksiyonları kontrol et ve uygula"""
        symbol = position['symbol']
        leverage = position['leverage']
        
        # Strategy manager'dan ne yapılması gerektiğini öğren
        action = self.strategy_manager.check_position_action(position, current_price)
        
        if action['action'] != 'hold':
            print(f"\n⚡ {symbol} - Aksiyon Tespit Edildi!")
            print(f"   Aksiyon: {action['action']}")
            print(f"   Sebep: {action['reason']}")
            
            # Aksiyonu uygula
            success = self.strategy_manager.execute_action(position, action, current_price)

            if success:
                print(f"   ✅ Aksiyon başarıyla uygulandı!")
    
    def _handle_exit_system(self, position: Dict, current_price: float, leverage: int):
        """Exit system'i ayrı kontrol et"""
        # TP type belirle
        rules = self.strategy_manager.get_rules_for_leverage(leverage)
        tp_type = rules.get('tp_type', 'standard')
        tp_rules = self.exit_system.get_tp_rules(tp_type)
        
        # TP1 kontrolü
        if self.exit_system.check_tp1(position, current_price, tp_rules):
            self.exit_system.execute_tp1(position, tp_rules)
        
        # TP2 kontrolü
        elif self.exit_system.check_tp2(position, current_price, tp_rules):
            self.exit_system.execute_tp2(position, tp_rules)
        
        # Trailing stop kontrolü
        elif self.exit_system.check_trailing_stop(position, current_price, tp_rules):
            self.exit_system.execute_trailing_stop(position)
    
    def monitor_positions(self):
        """Açık pozisyonları izle ve stream'leri başlat"""
        positions = self.position_manager.get_all_positions()
        
        if not positions:
            print("ℹ️  Henüz açık pozisyon yok")
            return
        
        print(f"\n📊 {len(positions)} açık pozisyon tespit edildi:")
        
        for pos in positions:
            symbol = pos['symbol']
            print(f"   • {symbol} - {pos['side']} - {pos['leverage']}x")
            
            # Stream başlat
            self.start_price_stream(symbol)
            
            # Exit system state'i başlat
            if symbol not in self.exit_system.position_states:
                self.exit_system.init_position_state(symbol, pos['entry_price'])
    
    def run(self):
        """Ana döngü - bot'u çalıştır"""
        self.running = True
        
        print("\n🟢 BOT ÇALIŞIYOR - Pozisyonlar izleniyor...")
        print("Durdurmak için Ctrl+C basın\n")
        
        try:
            while self.running:
                # Her 5 saniyede bir pozisyonları kontrol et
                self.monitor_positions()
                
                # Slot durumunu göster
                summary = self.account.get_account_summary()
                slot_info = self.position_manager.calculate_slot_usage(summary['total_usdt'])
                
                print(f"\r💰 Bakiye: {summary['total_usdt']} USDT | " 
                      f"🎰 Slot: {slot_info['used_slots']:.1f}/10 | "
                      f"📊 Pozisyon: {len(self.position_manager.get_all_positions())}", end="")
                
                time.sleep(5)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot durduruluyor...")
            self.stop()
    
    def stop(self):
        """Bot'u durdur"""
        self.running = False
        
        if self.twm:
            self.twm.stop()
            print("✅ WebSocket bağlantıları kapatıldı")
        
        print("✅ Bot başarıyla durduruldu")
        print("=" * 70)


# =====================================================
# ANA ÇALIŞTIRMA
# =====================================================

if __name__ == "__main__":
    bot = TradingBot()
    
    # Başlangıç özeti göster
    bot.position_manager.print_positions_summary()
    
    # Bot'u çalıştır
    bot.run()