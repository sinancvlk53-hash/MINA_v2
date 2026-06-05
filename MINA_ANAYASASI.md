# MINA v2 — Anayasa

> Tek kaynak: motor kuralları, Merter DCA, backlog ve dashboard gereksinimleri.
> Kod ve operasyon bu belgeye uygun geliştirilir.

---

## KASA VE SLOT HESABI (10 slot)

| Bölüm | Slot | Açıklama |
|-------|------|----------|
| **EI botu** | **2** | Merter 1x DCA — EI tarama (`merter_ei_1`, `merter_ei_2`) |
| **Merter diğer** | **1** | RSI bot + Merter standart sinyal yuvası (`merter_other`) |
| **Haluk Hoca** | **7** | 4x motor pipeline (K2/K3 onaylı sinyaller) |

- Kasa dinamiktir, sabit değildir
- 1 Slot = Kasa / 10
- İlk giriş marjini = Slot / 5 (%20)
- Kaldıraç = 4x (defans aktif, Haluk motor)
- Merter 1x DCA: ayrı bölüm, stop yok
- Sabit USDT değeri kod içinde **KESİNLİKLE YAZILMAZ**

---

## DERR — SİSTEM HAFIZASI

**DERR sistemin hafızasıdır. Her işlem buraya yazılır. Burası olmadan sistem kördür. Hiçbir pozisyon DERR'e yazılmadan açılmamalı veya kapanmamalıdır.**

- Manuel script, hedge test veya doğrudan Binance emirleri DERR dışı kalırsa motor pozisyonu “görmez”
- `log_trade_open` / `log_trade_close` zorunlu giriş noktalarıdır
- Hayalet pozisyon: `positionAmt=0` ama `isolatedMargin ≤ 0` → motor log + Telegram uyarısı

---

## TP ANAYASASI (4x Motor)

1x–9x kaldıraç (standard):

- TP1: giriş × 1.03 → %50 kapat
- TP1 sonrası stop breakeven'a çek
- TP2: giriş × 1.05 → %50 kapat
- Trailing: TRAILING_STOP_MARKET, callbackRate 2.0, activationPrice = TP2 fiyatı

10x kaldıraç (fast):

- TP1: giriş × 1.02 → %50 kapat
- TP2: giriş × 1.04 → %100 kapat
- Trailing: YOK

---

## STOP-LOSS (4x hariç)

| Kaldıraç | Stop |
|----------|------|
| 1x, 2x | %3 |
| 3x | %2 |
| 5x, 6x | %2 |
| 7x | %1.5 |
| 8x, 9x, 10x | %1 |
| **4x** | **DEFANS AKTİF (stop yok)** |

---

## DEFANS SİSTEMİ (sadece 4x)

Slot dağılımı (tek yuva içinde):

- Giriş: Slot / 5
- D1: Slot / 5
- D2: Slot / 5
- D3: Slot × 2/5

### D1

- Tetik: `current_price <= initial_entry × 0.95`
- Slot/5 kadar ekleme (market)
- TP sistemi devam eder, stop konmaz

### D2

- Tetik: `current_price <= initial_entry × 0.88`
- Slot/5 kadar ekleme
- TP dondurulur
- `be_price = weighted_avg × 1.0035` → TAKE_PROFIT_MARKET

### D3 — Hayalet SFP

- Önceden limit emir **KONMAZ**
- 4H destek tespiti (min 3 temas) — *dinamik algoritma backlog'da*
- 5m Bull Bar onayı zorunlu
- Slot×2/5 kadar ekleme
- Hard stop: SFP iğnesi altına

### D3 atlanırsa

- `current_price <= initial_entry × 0.75` → STOP_MARKET

### Hard stop patlarsa

- O coine 2 saat cooldown

### Restart / sync kuralı (uygulandı)

- `sync_reality_from_binance()` açık pozisyonlarda `defense_levels` ve `defense_stage` **sıfırlamaz**
- DERR `defense_triggered` ile restore edilir
- D1 idempotency: aynı seviye bir kez tetiklenir, tekrar market emir atılmaz

---

## KRİTİK KURALLAR

1. `initial_margins.json` her zaman gerçek marjini yansıtmalı
2. Pozisyon yeniden açılınca tracking dosyaları güncellenmeli
3. ROE yalnızca dashboard gösterimi içindir; D1/D2/D3/Hard Stop **spot fiyat** tetikleyicilidir
4. Tüm değerler dinamik hesaplanır; kasa değişince slot/marjin otomatik güncellenir
5. Testnet'te TRAILING_STOP_MARKET -4120 → engine-side manuel trailing (`max_prices.json` seed zorunlu)
6. Gerçek hesapta `/fapi/v1/order/algo/trailing` test edilmeden geçiş yapılmaz

---

## MERTER 1x DCA ANAYASASI

### Slot yapısı (10 slot)

- **2 slot** → EI tarama botu (`merter_ei_1`, `merter_ei_2`)
- **1 slot** → Merter diğer / RSI bot (`merter_other`)
- **7 slot** → Haluk Hoca 4x motor (ayrı bölüm)
- Her yuva kendi içinde **10 eşit parçaya** bölünür: `parça = slot_budget / 10`
- Kaldıraç: **1x ISOLATED**, stop yok, likidasyon riski yok (1x)

### Giriş ve DCA

- İlk giriş: **1 parça** market emri
- Kalan **9 parça**: her **%2 düşüşte** bir parça (sabit adım)
  - Örnek: giriş 100 → limitler 98, 96, … 82
- Limit emirler giriş anında borsaya dizilir

### EI bot filtresi

- RVOL = son kapalı 5m hacim / son 1 saat ortalama 5m hacmi
- RVOL ≥ **2.0** olan coinler arasından **en yüksek RVOL** seçilir
- RVOL ≥ 2.0 yoksa sinyal reddedilir

### RSI bot filtresi

- RSI(5dk) **< 20**
- Teyit: RSI 20 altına düştükten sonra 1–2 adet 5m mumda **+3 puan** yükseliş veya **20 kırılımı**
- Teyit yoksa reddet

### Ek filtreler (uygulandı)

- **24s hacim**: Binance futures quoteVolume ≥ **50M USD** (delist koruması)
- **Pump koruması**: RVOL birincisi son 15 dk **%5+** yükselmişse atla, sıradaki RVOL adayını dene
- **Çift teyit bonusu**: EI + RSI aynı coin (15 dk penceresi) → ilk giriş **2 parça**

### TP ve çıkış

- TP1: ortalama maliyet +**%3** → %50 kapat
- TP2: ortalama maliyet +**%5** → kalan %50 kapat
- Trailing: TP2 sonrası **%2** takip
- **48 saat timeout** → zararda kapatma yerine **breakeven modu**; fiyat maliyete gelince kapat

### Entegrasyon

- Modül: `signal_bot/merter_dca_manager.py`
- İzleme: `signal_bot/merter_dca_runner.py` / `mina-merter-dca.service`
- DERR: `signal_source` = `merter_ei` veya `merter_rsi`
- Telegram: EI/RSI bot mesajları listener → DCA manager (kuyruk bypass)

---

## OKUNACAKLAR — KOD DEĞİŞİKLİĞİ GEREKTİRİR

> Backlog. Uygulama öncesi DERR / test verisi ile doğrulanır.

### 1. D1/D2 sabit yüzdeler

- **Durum:** D1/D2 tetikleri şu an sabit çarpanlarla (`×0.95`, `×0.88`) çalışıyor
- **Karar:** **50 işlem** tamamlandıktan sonra DERR verisine bakılıp sabit mi dinamik mi kalacağına karar verilecek
- **Not:** Restart sonrası defense koruma fix'i uygulandı (`defense_levels` + D1 idempotency)

### 2. Merter / sinyal filtreleri (henüz kodlanmadı)

- **RSI > 70 → LONG reddet**
- **Fiyat EMA20 altında → LONG reddet**
- Cursor'a implementasyon görevi olarak yazılacak

### 3. 4H SFP — dinamik destek algoritması

- Sabit bölge yerine: **son 20–50 mumun en dip fitili** destek olarak alınacak
- Min 3 temas kuralı korunur
- D3 hayalet SFP onayı bu seviyeye bağlanır

---

## DASHBOARD GEREKSİNİMLERİ — KOD DEĞİŞİKLİĞİ GEREKTİRİR

### Merter DCA slotları

- Merter 1x DCA yuvaları (**EI + RSI**) 4x motor slotlarından **ayrı bölümde** gösterilmeli
- Her yuva: parça doluluk (örn. 3/10), sembol, ortalama maliyet, breakeven modu durumu

### RVOL gösterimi

- Pozisyon kartında ilgili coin için **güncel RVOL** değeri görünsün
- EI tarama geçmişi / son hesaplanan RVOL API veya WS üzerinden beslenebilir

---

## SUNUCU VE SERVİSLER

| Servis | Görev |
|--------|--------|
| `mina-engine.service` | 4x motor |
| `mina-merter-dca.service` | Merter DCA TP/trailing/breakeven |
| `mina-listener.service` | Telegram sinyal |
| `mina-queue-watcher.service` | Guillotine / kuyruk |
| `mina-dashboard-ws.service` | Dashboard WS |
| `mina-dashboard-vite.service` | Dashboard UI (port 3000) |

- Sunucu: `178.105.150.40`
- GitHub: [sinancvlk53-hash/MINA_v2](https://github.com/sinancvlk53-hash/MINA_v2)

---

## GERÇEK HESAP ÖNCESİ KONTROL

- [ ] Trailing stop Algo endpoint test
- [ ] D3 öncesi bakiye yeniden hesaplama
- [ ] Order retry mekanizması
- [ ] Slot limit fix
- [ ] D1/D2 dinamik mi sabit mi — 50 işlem DERR analizi
- [ ] RSI>70 / EMA20 LONG filtreleri
- [ ] 4H SFP dinamik destek
- [ ] Dashboard Merter slot + RVOL kartları
