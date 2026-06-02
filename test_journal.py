# -*- coding: utf-8 -*-
"""
DERR Trading Journal — Hızlı Test Scripti

Fake işlemler açıp kapatarak journal sisteminin çalışmasını test et.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from mina_trading_journal import TradingJournal
from datetime import datetime

def test_journal():
    """Journal sistemini test et."""
    
    print("\n" + "="*70)
    print("🧪 DERR TRADING JOURNAL TEST")
    print("="*70 + "\n")
    
    journal = TradingJournal(db_path='test_trades.db')
    
    # ─────────────────────────────────────────────────────────
    # İşlem 1: Başarılı LONG (TP2 ile kapatıldı)
    # ─────────────────────────────────────────────────────────
    print("📝 Test 1: Başarılı LONG (TP2 çıkışı)")
    trade1 = journal.log_trade_open(
        symbol='BTCUSDT',
        side='LONG',
        leverage=4,
        entry_price=77000.0,
        qty=0.00129,
        initial_margin=25.0
    )
    
    # D1 tetiklenmiş
    journal.log_defense_triggered(
        trade_id=trade1,
        defense_level=1,
        defense_prices={'D1': 73150, 'D2': 67760, 'D3': 57750},
        weighted_avg=76500.0
    )
    
    # TP2 ile kapat
    journal.log_trade_close(
        trade_id=trade1,
        close_price=78000.0,
        qty=0.00129,
        close_reason='TP2',
        pnl_usdt=40.50,
        pnl_percent=1.3,
        roe_percent=162.0
    )
    
    # ─────────────────────────────────────────────────────────
    # İşlem 2: Zarar (Hard Stop tetiklenmesi)
    # ─────────────────────────────────────────────────────────
    print("\n📝 Test 2: Zarar LONG (Hard Stop tetiklemesi)")
    trade2 = journal.log_trade_open(
        symbol='ETHUSDT',
        side='LONG',
        leverage=5,
        entry_price=3500.0,
        qty=0.05,
        initial_margin=35.0
    )
    
    # D2 + D3 tetiklenmişler
    journal.log_defense_triggered(
        trade_id=trade2,
        defense_level=2,
        defense_prices={'D1': 3325, 'D2': 3080, 'D3': 2625},
        weighted_avg=3450.0
    )
    
    journal.log_defense_triggered(
        trade_id=trade2,
        defense_level=3,
        defense_prices={'D1': 3325, 'D2': 3080, 'D3': 2625},
        weighted_avg=3400.0
    )
    
    # Hard Stop
    journal.log_trade_close(
        trade_id=trade2,
        close_price=2625.0,
        qty=0.05,
        close_reason='Hard Stop',
        pnl_usdt=-175.0,
        pnl_percent=-5.0,
        roe_percent=-500.0
    )
    
    # ─────────────────────────────────────────────────────────
    # İşlem 3: Trailing Stop ile kâr
    # ─────────────────────────────────────────────────────────
    print("\n📝 Test 3: Kâr SHORT (Trailing Stop)")
    trade3 = journal.log_trade_open(
        symbol='BNBUSDT',
        side='SHORT',
        leverage=3,
        entry_price=620.0,
        qty=0.1,
        initial_margin=20.67
    )
    
    # TP1 demi
    journal.log_trade_close(
        trade_id=trade3,
        close_price=615.0,
        qty=0.05,
        close_reason='TP1',
        pnl_usdt=25.0,
        pnl_percent=0.8,
        roe_percent=121.0
    )
    
    # ─────────────────────────────────────────────────────────
    # İşlem 4: Breakeven kaçış (D2 sonrası)
    # ─────────────────────────────────────────────────────────
    print("\n📝 Test 4: Başabaş kaçış (D2 kaçış emri)")
    trade4 = journal.log_trade_open(
        symbol='SOLUSDT',
        side='LONG',
        leverage=2,
        entry_price=180.0,
        qty=0.5,
        initial_margin=45.0
    )
    
    # D2 tetiklendi
    journal.log_defense_triggered(
        trade_id=trade4,
        defense_level=2,
        defense_prices={'D1': 171, 'D2': 158.4, 'D3': 135},
        weighted_avg=178.0
    )
    
    # Başabaş ile kapat
    journal.log_trade_close(
        trade_id=trade4,
        close_price=178.63,
        qty=0.5,
        close_reason='Başabaş',
        pnl_usdt=0.5,
        pnl_percent=0.04,
        roe_percent=1.1
    )
    
    # ─────────────────────────────────────────────────────────
    # İstatistikleri göster
    # ─────────────────────────────────────────────────────────
    print("\n" + "-"*70)
    journal.print_statistics(limit=100)
    
    # CSV dışa aktarma
    print("\n💾 CSV'ye dışa aktarılıyor...")
    journal.export_trades_csv(output_file='test_trades_export.csv')
    
    # Geçmiş görüntüle
    print("\n📜 Son 10 İşlem:")
    history = journal.get_trade_history(limit=10)
    for trade in history[:3]:  # İlk 3'ü göster
        print(f"   • {trade['symbol']} {trade['side']} {trade['leverage']}x | "
              f"PnL: ${trade['pnl_usdt']:+.2f} | "
              f"Çıkış: {trade['close_reason']}")
    
    print("\n✅ Test tamamlandı!")
    print("="*70 + "\n")
    
    journal.close()

if __name__ == '__main__':
    test_journal()
