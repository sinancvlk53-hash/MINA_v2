# DERR (Veri Tabanlı Öz-Denetim ve İşlem Günlüğü) — Trading Journal Implementasyonu

## Genel Bakış

**DERR (Veri Tabanlı Öz-Denetim ve İşlem Günlüğü)** — Başmimarın emriyle sisteme entegre edilen profesyonel **Trading Journal** modülü.

Amacı:
- ✅ **Audit Trail**: Botun açıp kapattığı HER işlemi mikrosaniye hassasiyetiyle kaydet
- ✅ **Veri Kaynağı**: 20'şer veya 100'er işlemlik örneklemlerle Başmüfettiş AI'ını optimize et
- ✅ **Metrikleme**: Savunma etkinliği, kaldıraç performansı, sembol analizi

---

## Mimari

### 1. **mina_trading_journal.py** — Çekirdek Modül

**SQLite Veritabanı Şeması:**

```sql
trades (
  id INTEGER PRIMARY KEY,
  
  -- Temel İşlem Bilgileri
  symbol TEXT,
  side TEXT (LONG/SHORT),
  leverage INTEGER (1x-10x),
  
  -- Açılış
  open_time TIMESTAMP,
  open_price REAL,
  open_qty REAL,
  open_notional REAL (fiyat × miktar),
  initial_margin REAL,
  
  -- Savunma (D1/D2/D3)
  defense_triggered INTEGER (0=Yok, 1=D1, 2=D2, 3=D3),
  defense_prices TEXT (JSON),
  weighted_avg_price REAL,
  
  -- Kapanış
  close_time TIMESTAMP,
  close_price REAL,
  close_qty REAL,
  close_reason TEXT (TP1/TP2/Trailing/Hard Stop/Başabaş/Acil Tasfiye),
  
  -- PnL Metrikleri
  pnl_percent REAL,
  pnl_usdt REAL,
  roe_percent REAL,
  
  -- Meta
  status TEXT (open/closed),
  created_at TIMESTAMP
)
```

**Ana Metodlar:**

```python
journal = TradingJournal()  # db_path='mina_trading_journal.db'

# İşlem Açılış
trade_id = journal.log_trade_open(
    symbol='BTCUSDT',
    side='LONG',
    leverage=4,
    entry_price=77000.0,
    qty=0.00129,
    initial_margin=25.0
)

# Savunma Tetiklemesi
journal.log_defense_triggered(
    trade_id=trade_id,
    defense_level=1,  # D1, D2, veya D3
    defense_prices={'D1': 73150, 'D2': 67760, 'D3': 57750},
    weighted_avg=76500.0
)

# İşlem Kapanışı
journal.log_trade_close(
    trade_id=trade_id,
    close_price=78000.0,
    qty=0.00129,
    close_reason='TP2',  # TP1, TP2, Trailing, Hard Stop, Başabaş, Acil Tasfiye
    pnl_usdt=40.50,
    pnl_percent=1.3,
    roe_percent=162.0
)

# İstatistikler
stats = journal.get_statistics(limit=100)
journal.print_statistics(limit=100)

# CSV Dışa Aktarma
journal.export_trades_csv(output_file='trades.csv')
```

---

### 2. **mina_position_manager.py** — Journal Entegrasyonu

**Journal Callback Lokasyonları (Tüm Çıkış Yolları Kapanmış):**

#### **TP1 Kapatması** (`execute_take_profit()`)
```python
# TP1: %50 pozisyon kapatılır
self.log_position_close(
    symbol=symbol,
    close_price=close_price,
    qty=close_qty,
    close_reason='TP1',
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_percent,
    roe_percent=roe_percent
)
```

#### **TP2 Kapatması**
```python
self.log_position_close(
    symbol=symbol,
    close_price=close_price,
    qty=close_qty,
    close_reason='TP2',
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_percent,
    roe_percent=roe_percent
)
```

#### **Trailing Stop** (`execute_trailing_stop()`)
```python
self.log_position_close(
    symbol=symbol,
    close_price=close_price,
    qty=amount,
    close_reason='Trailing',  # ← Trailing Stop
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_percent,
    roe_percent=roe_percent
)
```

#### **Hard Stop** (`execute_hard_stop()`)
```python
self.log_position_close(
    symbol=symbol,
    close_price=close_price,
    qty=amount,
    close_reason='Hard Stop',
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_percent,
    roe_percent=roe_percent
)
```

#### **Stop Loss** (`execute_stop_loss()`)
```python
self.log_position_close(
    symbol=symbol,
    close_price=close_price,
    qty=amount,
    close_reason='Stop Loss',
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_percent,
    roe_percent=roe_percent
)
```

#### **Acil Tasfiye** (`_emergency_close_overflow_positions()`)
```python
self.log_position_close(
    symbol=symbol,
    close_price=mark_price,
    qty=qty_to_close,
    close_reason='Acil Tasfiye',  # ← Slot kapısı açma
    pnl_usdt=pnl_usdt,
    pnl_percent=pnl_pct,
    roe_percent=roe_percent
)
```

#### **Savunma Etkinleştirme** (D1/D2/D3)
```python
# D1 çalıştırıldığında
self.log_defense_activation(
    symbol=symbol,
    defense_level=1,
    defense_prices={'D1': entry×0.95, 'D2': entry×0.88, 'D3': entry×0.75},
    weighted_avg=weighted_avg
)

# D2 çalıştırıldığında
self.log_defense_activation(
    symbol=symbol,
    defense_level=2,
    defense_prices={...},
    weighted_avg=weighted_avg
)

# D3 çalıştırıldığında
self.log_defense_activation(
    symbol=symbol,
    defense_level=3,
    defense_prices={...},
    weighted_avg=weighted_avg
)
```

---

### 3. **backend/main.py** — Bot Entegrasyonu

```python
from mina_trading_journal import TradingJournal

class TradingBot:
    def __init__(self):
        # Journal'ı başlat
        self.journal = TradingJournal()
        print("✅ Trading Journal başlatıldı")
        
        # MinaPositionManager'a journal'ı geç
        self.mina_manager = MinaPositionManager(
            client, 
            slot_size, 
            journal=self.journal  # ← Journal referansı
        )
    
    def monitor_positions(self):
        # Açık pozisyonları izlerken
        # Yeni açılmış işlemleri journal'a kaydet
        for pos in positions:
            if self.journal and symbol not in self.mina_manager.trade_ids:
                self.mina_manager.log_position_open(
                    symbol=symbol,
                    side=pos['side'],
                    leverage=pos['leverage'],
                    entry_price=pos['entry_price'],
                    qty=pos['quantity'],
                    initial_margin=pos['isolated_margin']
                )
    
    def stop(self):
        # Bot durduğunda istatistikleri göster
        if self.journal:
            print("\n📊 Trading Journal İstatistikleri:")
            self.journal.print_statistics(limit=100)
            self.journal.close()
```

---

## Kullanım Örnekleri

### Örnek 1: Test İşlem Kaydı

```python
journal = TradingJournal()

# İşlem 1: BTCUSDT LONG 4x - TP2 ile kâr
trade_id = journal.log_trade_open(
    symbol='BTCUSDT', side='LONG', leverage=4,
    entry_price=77000.0, qty=0.00129, initial_margin=25.0
)
journal.log_defense_triggered(trade_id, 1, {'D1': 73150}, 76500.0)
journal.log_trade_close(
    trade_id, close_price=78000.0, qty=0.00129,
    close_reason='TP2', pnl_usdt=40.50, pnl_percent=1.3, roe_percent=162.0
)

# İstatistikleri göster
journal.print_statistics()
```

**Çıktı:**
```
======================================================================
📊 TRADİNG JOURNAL İSTATİSTİKLERİ (Son 100 İşlem)
======================================================================

💰 ÖZET:
   Total PnL: $+40.50
   Başarılı: 1 | Başarısız: 0 | Başabaş: 0
   Başarı Oranı: 100.0%
   ...
```

### Örnek 2: Savunma Etkinliği Analizi

```python
stats = journal.get_statistics(limit=100)

print(f"Savunma Tetikleme Oranı: {stats['defended_trades']} işlem (%{stats['sample_size']*100:.1f})")
print(f"D1/D2/D3 Başarı Oranı: %{stats['defense_win_rate']:.1f}")
```

### Örnek 3: Kaldıraç Performansı

```python
stats = journal.get_statistics()

for leverage, data in stats['leverage_breakdown'].items():
    print(f"{leverage}x: {data['count']} işlem | "
          f"Total PnL: ${data['total_pnl']:.2f} | "
          f"Avg: ${data['avg_pnl']:.2f}")
```

### Örnek 4: AI Optimizasyon Örneği Çıkarma

```python
# 20 işlemlik örnek - Başmüfettiş için
sample_20 = journal.get_trade_history(limit=20)

# 100 işlemlik örnek - Daha kapsamlı analiz
sample_100 = journal.get_trade_history(limit=100)

# CSV'ye dışa aktar
journal.export_trades_csv('ai_training_data.csv', limit=100)
```

---

## Metrikleme ve Raporlama

### İstatistik Özeti

```
💰 ÖZET:
   • Total PnL (dolar): Net kazanç/zarar
   • Başarılı/Başarısız İşlem Oranı
   • Win Rate: Kârlı işlem yüzdesi
   • Ortalama Kâr: Başarılı işlemlerin ortalama PnL'si
   • Ortalama Zarar: Zararlı işlemlerin ortalama PnL'si
   • Kar Faktörü: Avg Win / Avg Loss (> 1.5 ideal)

🛡️  SAVUNMA ANALİZİ:
   • Tetiklenen: Kaç işlemde D1/D2/D3 çalıştığı
   • Defense Win Rate: Savunma tetiklenip kârlı çıkan işlem yüzdesi

⚙️  KALDIRAC BREAKDOWN:
   • Her kaldıraç seviyesi için:
     - İşlem sayısı
     - Total PnL
     - Ortalama PnL
     - Başarı sayısı

🏆 EN İYİ SEMBOLLER:
   • Top 5 sembol (total PnL'ye göre sıralanmış)
```

### CSV Dışa Aktarma

```python
journal.export_trades_csv(output_file='2025_trades.csv', limit=1000)
```

Kolonlar:
- id, symbol, side, leverage
- open_time, open_price, open_qty, open_notional, initial_margin
- defense_triggered, defense_prices, weighted_avg_price
- close_time, close_price, close_qty, close_reason
- pnl_percent, pnl_usdt, roe_percent, status, created_at

---

## Başmüfettiş AI Optimizasyon Akışı

1. **Veri Toplama** (Devam Eden)
   - Bot her işlemi kaydeder
   - 20-100 işlem örneğine ulaşılıncaya kadar bekle

2. **İstatistik Çıkarımı**
   ```python
   # 20 işlem örneği ile hızlı sektör testi
   stats_20 = journal.get_statistics(limit=20)
   
   # 100 işlem örneği ile kapsamlı analiz
   stats_100 = journal.get_statistics(limit=100)
   ```

3. **Sembol Optimizasyonu**
   ```python
   top_symbols = stats_100['top_symbols']
   # En iyi performans gösteren semboller için ağırlık artır
   ```

4. **Kaldıraç Tuning**
   ```python
   leverage_stats = stats_100['leverage_breakdown']
   # En düşük riski, en yüksek kar faktörü olan kaldıraç seviyesini belirle
   ```

5. **Savunma Stratejisi İyileştirme**
   ```python
   defense_effectiveness = stats_100['defense_win_rate']
   # D1/D2/D3 tetiklenme fiyatları dinamik olarak ayarla
   ```

---

## Kritik Noktalar

### 1. **Trade ID Yönetimi**
```python
# Position manager'da trade IDs tutulur
self.trade_ids: Dict[str, int] = {
    'BTCUSDT': 1,
    'ETHUSDT': 2,
    # ...
}

# Pozisyon kapanırken ID'den faydalanılır
if symbol in self.trade_ids:
    trade_id = self.trade_ids[symbol]
    self.journal.log_trade_close(trade_id, ...)
```

### 2. **PnL Hesaplaması**

**LONG için:**
```
pnl_usdt = (close_price - entry_price) × quantity
pnl_percent = (pnl_usdt / (entry_price × quantity)) × 100
roe_percent = (pnl_usdt / initial_margin) × 100
```

**SHORT için:**
```
pnl_usdt = (entry_price - close_price) × quantity
pnl_percent = (pnl_usdt / (entry_price × quantity)) × 100
roe_percent = (pnl_usdt / initial_margin) × 100
```

### 3. **Defans Durumu İzleme**
```python
state = self.position_states.get(symbol, {})
defense_stage = state.get('defense_stage', 0)  # 0=Yok, 1=D1, 2=D2, 3=D3
weighted_avg = state.get('weighted_avg_price')
```

### 4. **Çıkış Nedeni Standartizasyonu**
| Close Reason | Tetikleyen | Senaryo |
|---|---|---|
| **TP1** | TP sistem | İlk %50 kârlı kapatma |
| **TP2** | TP sistem | Kalan pozisyon kârlı kapatma |
| **Trailing** | Trailing Stop | Maksimum fiyat geriye çekilerek aktivasyon |
| **Hard Stop** | -75% loss | Devam eden zarar limiti |
| **Stop Loss** | -SL% | Kaldıraç spesifik SL |
| **Başabaş** | D2 kaçış | D2 tetiklenip breakeven fiyatına ulaştı |
| **Acil Tasfiye** | Slot kapısı | 10+ pozisyon overflow |

---

## Testler

### Birim Test: `test_journal.py`

```bash
python test_journal.py
```

**Test Senaryoları:**
1. ✅ Başarılı LONG (TP2 çıkışı)
2. ✅ Zarar LONG (Hard Stop)
3. ✅ SHORT Trailing Stop
4. ✅ Başabaş Kaçış (D2)

**Beklenen Sonuç:**
```
✅ 4 işlem kaydedildi
✅ Istatistikler hesaplandı (Win Rate: 75%)
✅ CSV dışa aktarıldı
✅ Test tamamlandı
```

---

## Gelecek Geliştirmeler

- [ ] Real-time WebSocket dashboard (işlem açılış/kapanış anında güncelleme)
- [ ] Grafik raporlama (Matplotlib/Plotly)
- [ ] Başmüfettiş AI integrasyon endpoint'i
- [ ] Özel metrik tasarımı (Sharpe Ratio, Drawdown, vb.)
- [ ] Çok hesaplı analiz (Her API key için ayrı journal)

---

## Kaynaklar

- [CLAUDE.md](CLAUDE.md) — MINA Anayasası
- [mina_position_manager.py](mina_position_manager.py) — Motor çekirdeği
- [backend/main.py](backend/main.py) — Bot orchestrasyonu
- [mina_trading_journal.py](mina_trading_journal.py) — Journal modülü

---

**Başmimarın Emriyle Oluşturulmuş — Başmüfettiş AI Optimizasyon İçin**

v1.0 | 2025
