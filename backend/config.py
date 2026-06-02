# -*- coding: utf-8 -*-
"""
MİNA v2 - Backend Konfigürasyon
Binance bağlantısı ve temel ayarlar
"""

import os
from binance.client import Client
from dotenv import load_dotenv

# .env dosyasını oku
load_dotenv()

# =====================================================
# BİNANCE BAĞLANTI AYARLARI
# =====================================================

class BinanceConfig:
    """Binance API bağlantı ayarları"""
    
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_SECRET_KEY')
        self.testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'

        if not self.api_key or not self.api_secret:
            raise ValueError("BINANCE_API_KEY veya BINANCE_SECRET_KEY .env dosyasında bulunamadı!")

        self.client = Client(self.api_key, self.api_secret, testnet=self.testnet)
    
    def get_client(self):
        """Binance client'ı döndür"""
        return self.client


# =====================================================
# HESAP YÖNETİMİ
# =====================================================

class AccountManager:
    """Hesap bakiyesi ve slot hesaplamaları"""
    
    def __init__(self, client):
        self.client = client
        self.slot_count = 10  # Sabit: 10 slot
    
    def get_usdt_balance(self):
        """
        Sadece USDT bakiyesini oku
        BTC, USDC gibi diğer coinler dikkate alınmaz
        """
        try:
            balance = self.client.futures_account_balance()
            
            for asset in balance:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
            
            return 0.0
        
        except Exception as e:
            print(f"Bakiye okuma hatası: {e}")
            return 0.0
    
    def calculate_slot_size(self):
        """
        Slot büyüklüğünü hesapla
        Toplam USDT / 10
        """
        total_usdt = self.get_usdt_balance()
        slot_size = total_usdt / self.slot_count
        return slot_size
    
    def calculate_entry_amount(self):
        """
        Giriş miktarını hesapla
        Slot'un %20'si
        """
        slot_size = self.calculate_slot_size()
        entry_amount = slot_size * 0.20
        return entry_amount
    
    def calculate_defense_amount(self):
        """
        Savunma miktarını hesapla
        Slot'un %80'i (sadece 4x için)
        """
        slot_size = self.calculate_slot_size()
        defense_amount = slot_size * 0.80
        return defense_amount
    
    def get_account_summary(self):
        """
        Hesap özetini döndür
        """
        total_usdt = self.get_usdt_balance()
        slot_size = self.calculate_slot_size()
        entry_amount = self.calculate_entry_amount()
        defense_amount = self.calculate_defense_amount()
        
        return {
            'total_usdt': round(total_usdt, 2),
            'slot_size': round(slot_size, 2),
            'entry_amount': round(entry_amount, 2),
            'defense_amount': round(defense_amount, 2),
            'slot_count': self.slot_count
        }


# =====================================================
# KALDIRAC AYARLARI
# =====================================================

class LeverageConfig:
    """Kaldıraç bazlı kurallar"""
    
    LEVERAGE_RULES = {
        1: {
            'name': '1x',
            'stop_loss_percent': 3,
            'has_defense': False
        },
        2: {
            'name': '2x',
            'stop_loss_percent': 3,
            'has_defense': False
        },
        3: {
            'name': '3x',
            'stop_loss_percent': 2,
            'has_defense': False
        },
        4: {
            'name': '4x (ANA)',
            'stop_loss_percent': None,
            'has_defense': True,
            'defense_1': 5,
            'defense_2': 10,
            'defense_3': True
        },
        5: {
            'name': '5x',
            'stop_loss_percent': 2,
            'has_defense': False
        },
        10: {
            'name': '10x',
            'stop_loss_percent': 1,
            'has_defense': False
        }
    }
    
    @staticmethod
    def get_rules(leverage):
        """Belirtilen kaldıraç için kuralları döndür"""
        return LeverageConfig.LEVERAGE_RULES.get(leverage, None)


# =====================================================
# KOMİSYON HESAPLAMA
# =====================================================

class CommissionCalculator:
    """Binance komisyon hesaplamaları"""
    
    MAKER_FEE = 0.0002  # %0.02
    TAKER_FEE = 0.0004  # %0.04
    
    @staticmethod
    def calculate_fee(amount, fee_type='taker'):
        """
        Komisyon hesapla
        amount: İşlem miktarı
        fee_type: 'maker' veya 'taker'
        """
        fee_rate = CommissionCalculator.TAKER_FEE if fee_type == 'taker' else CommissionCalculator.MAKER_FEE
        return amount * fee_rate
    
    @staticmethod
    def calculate_breakeven_with_fee(entry_price, amount):
        """
        Komisyonlu başabaş fiyatı hesapla (giriş + çıkış komisyonu toplam 2x taker fee)
        """
        return entry_price * (1 + 2 * CommissionCalculator.TAKER_FEE)


# =====================================================
# TEST KODU
# =====================================================

if __name__ == "__main__":
    print("=" * 50)
    print("MİNA v2 - CONFIG TEST")
    print("=" * 50)
    
    # Binance bağlantısı
    print("\n1. Binance Bağlantısı Test Ediliyor...")
    config = BinanceConfig()
    client = config.get_client()
    print("✅ Binance Client Oluşturuldu")
    
    # Hesap yöneticisi
    print("\n2. Hesap Bilgileri Okunuyor...")
    account = AccountManager(client)
    summary = account.get_account_summary()
    
    print("\n📊 HESAP ÖZETİ:")
    print(f"   💰 Toplam USDT: {summary['total_usdt']} USDT")
    print(f"   📦 Slot Sayısı: {summary['slot_count']}")
    print(f"   🎯 Slot Büyüklüğü: {summary['slot_size']} USDT")
    print(f"   🚀 Giriş Miktarı (Slot'un %20): {summary['entry_amount']} USDT")
    print(f"   🛡️  Savunma Bütçesi (Slot'un %80): {summary['defense_amount']} USDT")
    
    # Kaldıraç kuralları
    print("\n3. Kaldıraç Kuralları:")
    for lev in [1, 2, 3, 4, 5, 10]:
        rules = LeverageConfig.get_rules(lev)
        print(f"   {rules['name']}: Stop-Loss={rules.get('stop_loss_percent', 'Yok')}%, Savunma={rules['has_defense']}")
    
    # Komisyon testi
    print("\n4. Komisyon Hesaplama Testi:")
    test_amount = 100
    maker_fee = CommissionCalculator.calculate_fee(test_amount, 'maker')
    taker_fee = CommissionCalculator.calculate_fee(test_amount, 'taker')
    print(f"   100 USDT işlem için:")
    print(f"   Maker Fee: {maker_fee} USDT (%0.02)")
    print(f"   Taker Fee: {taker_fee} USDT (%0.04)")
    
    print("\n" + "=" * 50)
    print("✅ TÜM TESTLER BAŞARILI!")
    print("=" * 50)