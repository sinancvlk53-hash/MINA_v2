# MINA v2 — Motor Anayasası

## KASA VE SLOT HESABI
- Kasa dinamiktir, sabit değildir
- 1 Slot = Kasa / 10
- İlk giriş marjini = Slot / 5
- Kaldıraç = 4x (defans aktif)
- Hacim = Marjin × 4
- ÖRNEK: 4400 USDT kasa →
  Slot: 440 USDT →
  Marjin: 88 USDT →
  Hacim: 352 USDT
- 20 USDT veya sabit değer
  KESİNLİKLE YAZILMAZ

## TP ANAYASASı
1x-9x kaldıraç (standard):
- TP1: giriş × 1.03 → %50 kapat
- TP1 sonrası stop breakeven'a çek
- TP2: giriş × 1.05 → %50 kapat
- Trailing: TRAILING_STOP_MARKET
  callbackRate: 2.0
  activationPrice: TP2 fiyatı

10x kaldıraç (fast):
- TP1: giriş × 1.02 → %50 kapat
- TP2: giriş × 1.04 → %100 kapat
- Trailing: YOK

## STOP-LOSS (4x hariç)
1x=%3, 2x=%3, 3x=%2
5x=%2, 6x=%2, 7x=%1.5
8x=%1, 9x=%1, 10x=%1
4x: DEFANS AKTİF (stop yok)

## DEFANS SİSTEMİ (sadece 4x)
Slot dağılımı:
- Giriş: Slot / 5
- D1: Slot / 5
- D2: Slot / 5
- D3: Slot × 2/5

D1: current_price <= initial_entry × 0.95
- Slot/5 kadar LONG ekle
- TP sistemi devam eder
- Stop konmaz

D2: current_price <= initial_entry × 0.88
- Slot/5 kadar LONG ekle
- TP DONDURULUR
- be_price = weighted_avg × 1.0035
- TAKE_PROFIT_MARKET at

D3: Hayalet SFP
- Önceden limit emir KONMAZ
- 4H destek tespiti (min 3 temas)
- 5m Bull Bar onayı zorunlu
- Slot×2/5 kadar LONG ekle
- d3_be = yeni_ortalama × 1.0035
- D2 emri iptal et
- Hard stop: SFP iğnesi altına

D3 atlanırsa:
- current_price <= initial_entry × 0.75
- STOP_MARKET anında at

Hard stop patlarsa:
- O coine 2 saat cooldown

## KRİTİK KURALLAR
1. initial_margins.json her zaman
   gerçek marjini yansıtmalı
2. Pozisyon yeniden açılınca
   tracking dosyaları güncellenmeli
3. ROE hesabı initial_margin
   üzerinden yapılır (sadece
   dashboard gösterimi için).
   D1, D2, D3 ve Hard Stop
   tetikleyicileri KESİNLİKLE
   ROE'ye göre DEĞİL, doğrudan
   SPOT FİYAT üzerinden çalışır:
   D1: current_price <= initial_entry × 0.95
   D2: current_price <= initial_entry × 0.88
   D3: Hayalet SFP onayı
   Hard Stop: initial_entry × 0.75
4. Sabit USDT değeri kod içinde
   KESİNLİKLE YAZILMAZ
5. Tüm değerler dinamik hesaplanır
6. Kasa değişince slot ve marjin
   otomatik yeniden hesaplanır

## SUNUCU
IP: 178.105.150.40
Servisler:
- mina-engine.service
- mina-dashboard-ws.service
- mina-dashboard-vite.service
Dashboard: port 3000
GitHub: sinancvlk53-hash/MINA_v2
