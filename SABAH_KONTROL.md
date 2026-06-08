# MINA v2 — Sabah Kontrol Komutları

## 1. Zombie process kontrolü (EN ÖNEMLİ)
```bash
ps aux | grep python | grep -v grep
```
Beklenen: sadece mina-engine, mina-merter-dca, mina-listener, mina-dashboard-ws

## 2. Tüm servisler aktif mi
```bash
systemctl is-active mina-engine mina-listener mina-merter-dca mina-queue-watcher mina-dashboard-ws mina-dashboard-vite mina-haluk-yayin
```

## 3. Son log kontrolü
```bash
tail -20 /root/MINA_v2/mina_bot.log
```

## 4. Rate limit hatası var mı
```bash
grep -c "1003" /root/MINA_v2/mina_bot.log
```

## 5. Database lock var mı
```bash
grep -c "database is locked" /root/MINA_v2/mina_bot.log
```

## 6. Transkript durumu
```bash
ls /root/MINA_v2/signal_bot/history/transcripts/ | wc -l
```

## 7. Anormal pozisyon kontrolü (lot sayısı)
```bash
cd /root/MINA_v2 && venv/bin/python -c "
from binance.client import Client
import os
c = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
pos = [p for p in c.futures_position_information() if float(p['positionAmt']) != 0]
for p in pos:
    print(p['symbol'], float(p['positionAmt']), float(p['isolatedMargin']))
"
```
