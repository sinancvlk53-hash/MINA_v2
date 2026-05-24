# -*- coding: utf-8 -*-
"""Son işlemleri kontrol et"""

from config import BinanceConfig
from datetime import datetime

config = BinanceConfig()
client = config.get_client()

print("=" * 60)
print("📜 SON 10 İŞLEM GEÇMİŞİ")
print("=" * 60)

# Son işlemleri al
trades = client.futures_account_trades(symbol='BTCUSDT', limit=10)

if not trades:
    print("\n❌ Hiç işlem bulunamadı!")
else:
    for trade in trades:
        time = datetime.fromtimestamp(trade['time'] / 1000)
        print(f"\n⏰ {time}")
        print(f"   Yön: {'🟢 BUY' if trade['buyer'] else '🔴 SELL'}")
        print(f"   Miktar: {trade['qty']} BTC")
        print(f"   Fiyat: ${trade['price']}")
        print(f"   Komisyon: {trade['commission']} {trade['commissionAsset']}")
        print(f"   PnL: {trade.get('realizedPnl', 'N/A')} USDT")