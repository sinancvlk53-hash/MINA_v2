# Gerçek Hesaba Geçiş Kontrol Listesi

## Kod Değişiklikleri

- [ ] `.env` dosyasında `BINANCE_TESTNET=false` yap
- [ ] Gerçek Binance API key ve secret'ı `.env`'e yaz
- [ ] `backend/_raw_order.py` içindeki testnet URL'sini kaldır
- [ ] Trailing algo endpoint test et (`/fapi/v1/order/algo/trailing`)

## Test Edilmesi Gerekenler

- [ ] D3 savunması en az 1 kez test edilmeli
- [ ] Trailing stop canlıda test edilmeli
- [ ] 50 işlem DERR verisi biriktirilmeli, Expectancy pozitif olmalı
- [ ] Slot limit edge case'leri test edilmeli

## Güvenlik

- [ ] `.env` dosyasını güvenli yere yedekle (Google Drive veya şifreli not)
- [ ] API key'leri kimseyle paylaşma
- [ ] Sunucu SSH şifresini değiştir

## Risk Yönetimi

- [ ] İlk hafta maksimum 2 slot aç
- [ ] Günlük zarar limiti belirle
- [ ] Stop mekanizması test edilmeli

## Yapılacaklar Sonrası

- [ ] Dashboard URL'sini güvenli bağlantıya al (HTTPS)
- [ ] Sunucu monitoring ekle
