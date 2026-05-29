# MİNA v2 - SİSTEM KURALLARI

## GENEL BİLGİLER
- **Platform:** Binance Futures (Testnet)
- **Mod:** Hedge (Aynı coin'de hem Long hem Short açılabilir)
- **Bakiye:** Demo hesaptaki tutar baz alınır (örnek: 9487 USDT)
- **Slot Sayısı:** 10 eşit parça
- **Maksimum Pozisyon:** Aynı anda 10 farklı coin

---

## HESAPLAMA SİSTEMİ

### Bakiye Bölümü
- Toplam bakiye 10 eşit slot'a bölünür
- Örnek: 9487 USDT / 10 = **948.7 USDT/slot**

### Giriş Miktarı
- Her slot'un **%20'si** ile giriş yapılır
- Kalan **%80** savunmada bekler (sadece 4x'te kullanılır)
- Örnek: 948.7 * 0.20 = **189.74 USDT giriş**

---

## KALDIRAC SEÇENEKLERİ

### 1x KALDIRAC
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** YOK
- **Stop-Loss:** %3 düşüş → Otomatik kapat

### 2x KALDIRAC
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** YOK
- **Stop-Loss:** %3 düşüş → Otomatik kapat

### 3x KALDIRAC
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** YOK
- **Stop-Loss:** %3 düşüş → Otomatik kapat

### 4x KALDIRAC (ANA STRATEJİ)
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** 3 Aşamalı Sistem
  - 1. Savunma: %5 düşüş → Slot'un %20'si ekle
  - 2. Savunma: Likidasyonun %10 üstü → Slot'un %30'u ekle, sıfırda çık
  - 3. Savunma: Kalan %30 marjine ekle, sıfırda çık
    > D3 break-even: ROE >= -2% olduğunda kapatılır. Tam 0% değil — komisyon + slippage için -%2 emniyet payı. 4x kaldıraçta coin fiyatında sadece %0.5 fark eder.
- **Stop-Loss:** YOK (savunma sistemi var)

### 5x KALDIRAC
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** YOK
- **Stop-Loss:** %2 düşüş → Otomatik kapat

> **NOT:** 4x dışındaki tüm kaldıraçlarda defense sistemi aktif değildir. Stop Loss ile çalışır.

### 10x KALDIRAC
- **Giriş:** Slot'un %20'si
- **Kar Alma:** Normal kurallar (%3, %5, takipli)
- **Savunma:** YOK
- **Stop-Loss:** %1 düşüş → Otomatik kapat

---

## KÂR ALMA SİSTEMİ (TÜM KALDIRAÇLAR)

### 1. Adım: %3 Kâr
- Pozisyonun **%50'sini** sat
- Stop-Loss'u **breakeven'a** çek (komisyon dahil)
- Artık zarar edilemez

### 2. Adım: %5 Kâr
- Kalan pozisyonun **%50'sini** sat
- Toplam pozisyonun **%25'i** kalır

### 3. Adım: Takipli Stop
- Kalan %25 için takip başlat
- Fiyat **%1 geri** dönerse otomatik kapat

---

## KOMİSYON KORUMASI

- **Her işlemde** Binance komisyonları hesaplanır
  - Maker: %0.02
  - Taker: %0.04
- **Breakeven** hesabına komisyon dahil edilir
- **Kasa asla eksi göstermez**

---

## BİLEŞİK BÜYÜME

- Her kapanan işlemden kâr Futures hesabında kalır
- Hesap büyüdükçe slot büyüklüğü otomatik artar
- Örnek:
  - Bakiye 9487 USDT → Slot 948.7 USDT → Giriş 189.74 USDT
  - Bakiye 15000 USDT → Slot 1500 USDT → Giriş 300 USDT

---

## ÖZEL NOTLAR

- **Spot Transfer:** Demo hesapta devre dışı (gerçek hesapta %50 kâr Spot'a gidecek)
- **Manuel Giriş:** Sinan coin giriş/çıkış değerlerini manuel girecek
- **Hedef:** 1 sene içinde 1 milyon dolar

---

## HALUK HOCA PDF SİSTEMİ KURALLARI

### Kaldıraç
- **BTC, ETH, XAU, XAG** → 5x
- **Altcoinler** → 2x

### Giriş
- PDF'deki giriş fiyatı/bölgesi kullanılır

### D1 (İlk Ekleme)
- PDF'deki **stop seviyesine fiyat gelince** tetiklenir
- **ROE bazlı değil, fiyat bazlı!**
- D1 sonrası yeni ortalamaya göre TP güncellenir

### TP Sistemi (4x ile aynı)
- **TP1:** Yeni ortalamadan +%3
- **TP2:** Yeni ortalamadan +%5
- **Trailing:** Tepeden -%1

### Filtre Sistemi
- TOTAL yukarı + OTHERS güçlü → LONG aç
- TOTAL aşağı + OTHERS zayıf → SHORT aç
- TOTAL, OTHERS, BRENT, XCU → işlem açma, **sadece filtre**

### Sinyal Kuralı
- Grafik + giriş kutusu + stop seviyesi varsa → **aç**
- "Pas", "şu an değil" yazsa bile grafik varsa → **aç**
- TOTAL, OTHERS, BRENT, XCU → **asla açma**
## GENEL BİLGİLER
- **Platform:** Binance Futures (Testnet)
- **Para Birimi:** SADECE USDT (BTC, USDC, diğerleri kullanılmaz)
- **Mod:** Hedge (Aynı coin'de hem Long hem Short açılabilir)
- **Bakiye:** Demo hesaptaki USDT tutarı baz alınır (örnek: 4487 USDT)
- **Slot Sayısı:** 10 eşit parça
- **Maksimum Pozisyon:** Aynı anda 10 farklı coin
