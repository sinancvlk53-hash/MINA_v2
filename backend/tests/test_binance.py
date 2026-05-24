# -*- coding: utf-8 -*-
from binance.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')

print("=" * 50)
print("BINANCE TESTNET BAĞLANTI TESTİ")
print("=" * 50)

client = Client(api_key, api_secret, testnet=True)

try:
    balance = client.futures_account_balance()
    
    print("\nBAĞLANTI BAŞARILI!")
    print("\nFUTURES HESAP BAKİYESİ:")
    print("-" * 50)
    
    for asset in balance:
        if float(asset['balance']) > 0:
            print(f"{asset['asset']}: {asset['balance']}")
    
    print("-" * 50)
    print("\nTest tamamlandı!")
    
except Exception as e:
    print(f"\nHATA: {e}")
    