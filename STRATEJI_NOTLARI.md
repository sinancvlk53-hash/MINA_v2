# MINA v2 — Strateji Notları
## Veri Kaynakları
- EI Trading Bot: 15dk + 1s AL/SAT sinyalleri
- RSI Odası: Aşırı satılmış/alınmış filtresi

## Test Stratejileri
### 6x — Sinan'ın Stratejisi
- Stop: YOK
- D1: -4% ROE
- D2: -10% ROE
- TP1: +3% ROE → %50 kapat
- TP2: +5% ROE → kalan %50
- Trailing: -1%

### 3x — Merter'in Kuralları  
- Stop: -%2 coin
- TP1: +4.6% coin (2.30R)
- Trailing: -1%

## Backtest Sonuçları — Özet

### EI Bot (8 Altın Coin, 1s, LONG only)
- 3x: WR %44, ROE +3.01% ✅
- 6x: WR %73, ROE +1.06% ✅
- Max kayıp serisi 3x: 13 (26-27 Mayıs krizi)

### RSI + EI Gecikmeli Confluence
- Genel: 3x %34.8, 6x zararda ❌
- RUNEUSDT: 24 işlem, %71 WR ✅
- JUPUSDT: 12 işlem, %83 WR ✅
- SUNUSDT, BCHUSDT, TRXUSDT: kesinlikle alma ❌

### Kara Liste
SUNUSDT, BCHUSDT, TRXUSDT

### İzleme Listesi
AVAXUSDT, DYDXUSDT, JUPUSDT, RUNEUSDT

## Veri Gelince Bakılacaklar
- Win rate her strateji için
- Ortalama ROE
- En iyi saatler
- En iyi coinler
- Max drawdown
