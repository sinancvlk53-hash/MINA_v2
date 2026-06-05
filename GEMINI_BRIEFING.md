# MINA v2 — Gemini Briefing

> **Son güncelleme:** 2026-06-05  
> **Amaç:** Projeye yeni giren bir AI/agent için tek dosyada tam bağlam: mimari, kurallar, çözülen sorunlar, açık backlog, operasyon.  
> **Sunucu:** `178.105.150.40` · **Repo:** [sinancvlk53-hash/MINA_v2](https://github.com/sinancvlk53-hash/MINA_v2)  
> **Anayasa kaynakları:** `CLAUDE.md`, `MINA_ANAYASASI.md`

---

## 1. Proje Özeti ve Amacı

**MINA v2**, Binance Futures üzerinde çalışan, çok kaynaklı sinyal güdümlü otomatik trading motorudur.

| Hedef | Açıklama |
|-------|----------|
| **Otomasyon** | Telegram sinyalleri → filtre → pozisyon açma → TP/trailing/savunma → DERR kaydı |
| **Risk yönetimi** | 10 slotlu dinamik kasa, 4x motor savunma (D1/D2/D3), Merter 1x DCA ayrı bölüm |
| **Öz-denetim (DERR)** | Her açılış/kapanış SQLite journal'a; sistem kördür DERR olmadan |
| **İnsan gözetimi** | React dashboard (port 3000), WebSocket canlı veri, manuel açılış, motor pause |

**İki ana trading hattı:**

1. **4x Motor (Haluk pipeline)** — 7 slot Haluk + 1 slot Merter legacy → `main.py` / `MinaPositionManager`
2. **Merter 1x DCA** — 3 slot (2 EI + 1 RSI/diğer) → `merter_dca_manager.py` / ayrı servis

Eski monolitik `engine/main.py` **`_archive/`** altına taşındı. Tek motor girişi: **`main.py`**.

---

## 2. Sistem Mimarisi

### 2.1 Bileşen haritası

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM KAYNAKLARI                              │
│  Haluk Hoca kanalı  │  Merter kanalı (EI bot / RSI bot / legacy chat)   │
└──────────┬──────────────────────────────┬───────────────────────────────┘
           │                              │
           ▼                              ▼
   signal_bot/listener.py          signal_bot/listener.py
           │                              │
           ├─ haluk_pdf_parser ───────────┤
           │  signal_parser.py            ├─► merter_dca_manager (1x DCA)
           │  raw_signal_queue.json       │       │
           │                              │       ▼
           ▼                              │   merter_dca_runner (TP/BE)
   queue_watcher.py (audit)              │
           │                              │
           ▼                              │
   signal_guillotine (K2/K3)             │
           │                              │
           ▼                              │
   signal_slot_bridge.py ────────────────┼──► main.py (4x motor)
           │                              │       │
           ▼                              │       ▼
   mina_position_manager.py ◄────────────┘   mina_trading_journal.db (DERR)
           │
           ▼
   Binance Futures API (ISOLATED, LONG/SHORT)
           │
           ▼
   dashboard_ws.py (WS :8765) ──► React dashboard (:3000)
```

### 2.2 Servisler (systemd)

| Servis | Dosya / Rol |
|--------|-------------|
| `mina-engine.service` | `main.py` — 4x motor döngüsü (30s), sync, ghost scan |
| `mina-merter-dca.service` | `merter_dca_runner.py` — 1x DCA TP/trailing/48h BE, 5dk reconcile |
| `mina-listener.service` | `signal_bot/listener.py` — Telegram dinleyici |
| `mina-queue-watcher.service` | `queue_watcher.py` — K2/K3 karar logu |
| `mina-dashboard-ws.service` | `dashboard/dashboard_ws.py` — WS veri |
| `mina-dashboard-vite.service` | Dashboard UI — port **3000** |

Deploy: `scripts/deploy_full.py`

### 2.3 4x Motor (`MinaPositionManager`)

**Dosya:** `mina_position_manager.py`  
**Döngü:** `evaluate_position()` → `execute_action()`

| Aksiyon | Koşul | Not |
|---------|-------|-----|
| **Savunma D1** | `mark ≤ initial_entry × 0.95` (LONG) | Slot/5 ekleme, TP devam |
| **Savunma D2** | `mark ≤ initial_entry × 0.88` | Slot/5 ekleme, TP dondur, BE emri |
| **Savunma D3** | 4H SFP + 5m bull bar | Slot×2/5 ekleme, hayalet |
| **Hard Stop** | `mark ≤ initial_entry × 0.75` | Tam kapanış, 2s coin cooldown |
| **Stop Loss** | Kaldıraç bazlı % (4x hariç) | — |
| **TP1** | giriş × 1.03 → %50 kapat | BE stop |
| **TP2** | giriş × 1.05 → %50 kapat | — |
| **Trailing** | Engine-side `max_prices.json` | Testnet'te algo trailing -4120 |

**4x özel:** Stop-loss yok → savunma aktif.

**Merter 1x istisna:** `ghost_positions.is_merter_dca_position()` → motor `hold` (TP/stop/savunma uygulanmaz).

### 2.4 Savunma sistemi (4x only)

Slot dağılımı (tek yuva içinde):

| Parça | Marjin | Tetik (LONG spot) |
|-------|--------|-------------------|
| Giriş | Slot / 5 | — |
| D1 | Slot / 5 | initial × 0.95 |
| D2 | Slot / 5 | initial × 0.88 |
| D3 | Slot × 2/5 | Hayalet SFP onayı |

**Kritik:** Tetikleyiciler **ROE değil spot fiyat**. ROE yalnızca dashboard.

**State dosyaları:** `defense_levels.json`, `initial_entry_prices.json`, `initial_margins.json`, `position_states.json`

**Restart koruması:** `sync_reality_from_binance()` defense_levels ve DERR `defense_triggered` ile restore eder; D1 idempotency (`defense_stage >= 1` → tekrar emir yok).

### 2.5 Merter 1x DCA

**Modül:** `signal_bot/merter_dca_manager.py`  
**Yuvalar:** `merter_ei_1` (süzgeçli), `merter_ei_2` (süzgeçsiz), `merter_other` (RSI)

| Kural | Değer |
|-------|-------|
| Kaldıraç | 1x ISOLATED, stop yok |
| Parça | slot_budget / 10 |
| İlk giriş | 1 parça MARKET + 9 LIMIT (%2 adım: 98,96…82) |
| EI filtresi | RVOL ≥ 2.0, 24s hacim ≥ 50M USD, pump koruması, EMA20, S/R, SFP |
| RSI filtresi | RSI(5m) < 20 + teyit (+3 puan veya 20 kırılım) |
| Çift teyit | EI+RSI aynı coin 15dk → 2 parça giriş |
| TP1/TP2 | +3% %50, +5% kalan + %2 trailing |
| Timeout | Dashboard `merterTimeStopH` (varsayılan 4h) → breakeven modu |

**State:** `signal_bot/merter_dca_state.json`  
**Log:** `signal_bot/merter_dca.log`, `merter_dca_filter.log`

**Reconcile:** Her 5 dk `reconcile_state_from_derr()` — DERR + Binance ile state senkronu.

Detaylı akış: `MERTER_SIGNAL_FLOW.md`

### 2.6 Haluk PDF / Telegram

**Parser:** `signal_bot/haluk_pdf_parser.py`, `signal_parser.py`

- Haluk Telegram mesajları → macro seviyeler, coin sinyalleri
- PDF raporları → `parse_haluk_pdf_path()`
- Makro panel: `macro_levels_store.py` → `macro_levels.json`
- Onaylı sinyaller → `raw_signal_queue.json` → giyotin → slot bridge

**Kaynak kodları:** `HT` (Haluk), `MZ` (Merter), `MANUEL`, `yetim` (orphan sync)

---

## 3. Slot Yapısı ve Kasa Kuralları

**Politika dosyası:** `mina_slot_policy.py`

| Bölüm | Slot | Yuvalar |
|-------|------|---------|
| Haluk 4x motor | **7** | `MOTOR_SLOT_MAX` içinde |
| Merter 4x legacy | **1** | Kuyruk köprüsü |
| Merter EI DCA | **2** | `merter_ei_1`, `merter_ei_2` |
| Merter diğer DCA | **1** | `merter_other` (RSI) |
| **Toplam** | **10** | — |

### Kasa formülleri (ASLA sabit USDT yazılmaz)

```
Kasa     = Binance futures bakiye (dinamik)
1 Slot   = Kasa / 10
Giriş marjini (4x) = Slot / 5   (%20)
Hacim    = Marjin × Kaldıraç
```

**Örnek:** 4400 USDT kasa → Slot 440 → Marjin 88 → Hacim 352 (4x)

### Slot köprüsü kuralları

- Max açık motor pozisyonu: **8** (`MOTOR_SLOT_MAX`)
- Manuel açılış limiti: **10** (dashboard)
- Kuyruk TTL: **30 dakika** (`QUEUE_TTL_SEC = 1800`)
- Pozisyon kapanınca `try_fill_freed_slot()` en yüksek parlaklıklı onaylı sinyali tüketir

---

## 4. Çözülen Kritik Buglar

| # | Sorun | Çözüm | Dosya |
|---|-------|-------|-------|
| 1 | Eski `engine/main.py` dağınık mimari | Tek çekirdek `main.py` + `MinaPositionManager` | `main.py`, `_archive/` |
| 2 | Restart sonrası defense sıfırlanıyordu | `sync_reality_from_binance()` defense preserve + DERR restore | `mina_position_manager.py` |
| 3 | D1 tekrar tekrar market emir | Idempotency: `defense_stage >= 1` skip | `_execute_d1()` |
| 4 | Motor Merter 1x'e TP/stop uyguluyordu | `is_merter_dca_position()` → hold | `ghost_positions.py`, `evaluate_position()` |
| 5 | Hayalet pozisyon spam | `scan_and_report()` + Merter tracked keys | `backend/ghost_positions.py` |
| 6 | Eski kuyruk sinyali saatler sonra tüketiliyordu (BTC) | 30dk queue TTL | `signal_slot_bridge.py` |
| 7 | Merter state kaybı | 5dk `reconcile_state_from_derr()` | `merter_dca_runner.py` |
| 8 | Motor stop sonrası DCA limitleri kalıyordu (ZRO) | `log_position_close()` → `_cancel_merter_dca_limits()` | `mina_position_manager.py` |
| 9 | Yetim pozisyon `signal_source=None` | `detect_orphan_signal_source()` → MZ veya `yetim` | `mina_signal_source.py` |
| 10 | Testnet trailing -4120 | Engine-side trailing + `max_prices.json` seed | `check_trailing_stop()` |
| 11 | D2/D3 eşik hataları (eski) | -10%→-15%, -15%→-25% düzeltme | `GUNCEL_NOTLAR.md` |
| 12 | Haluk kısa ticker (AVAX→AVAXUSDT) | Parser düzeltmesi | `signal_parser.py` |
| 13 | Journal `signal_source` eksik | Kolon + Merter yuva id yazımı | `mina_trading_journal.py` |

---

## 5. Mevcut Açık Sorunlar ve Backlog

### 🔴 Operasyonel / acil

| Sorun | Durum | Not |
|-------|-------|-----|
| **BTC LONG D1 tetiklendi ama ekleme yok** | Açık | `defense_levels.json=1` ama qty 0.005; idempotency erken set edilmiş olabilir |
| **Motor 1x pozisyonlara stop_loss** | Kısmen | Ghost skip var; yetim/orphan 1x hâlâ risk (ZRO vakası) |
| **Merter DCA limit orphan** | Kısmen | Motor kapanışta iptal eklendi; geçmiş yetimler manuel temizlik |
| **initial_entry_prices.json eksik** | Açık | Sunucuda dosya yok; sync entry'den seed ediyor |

### 🟡 Backlog (`MINA_ANAYASASI.md`)

- [ ] D1/D2 sabit % vs dinamik — **50 işlem DERR analizi** sonrası karar
- [ ] RSI > 70 → LONG reddet (Merter)
- [ ] Fiyat EMA20 altında → LONG reddet (Merter)
- [ ] 4H SFP dinamik destek algoritması (son 20–50 mum dip fitili)
- [ ] Dashboard: Merter yuva parça doluluk (3/10), RVOL kartı
- [ ] Trailing algo endpoint gerçek hesap testi (`/fapi/v1/order/algo/trailing`)
- [ ] D3 öncesi bakiye yeniden hesaplama
- [ ] Order retry mekanizması
- [ ] Global risk limiti
- [ ] Backtest sistemi
- [ ] Hetzner Frankfurt prod sunucu (gerçek hesap)

### 🟢 Gerçek hesap öncesi checklist

- Trailing algo endpoint test edilmedi
- Slot limit edge case'leri
- Merter/Motor çakışma senaryoları (aynı sembol iki hat)

---

## 6. DERR Sistemi

**DERR** = *Veri Tabanlı Öz-Denetim ve İşlem Günlüğü*  
**Dosya:** `mina_trading_journal.py` → `mina_trading_journal.db` (SQLite)

### Neden kritik?

> *"DERR sistemin hafızasıdır. Burası olmadan sistem kördür."* — `MINA_ANAYASASI.md`

- Motor sync, raporlama, Merter reconcile, dashboard PnL — hepsi DERR'e dayanır
- DERR dışı Binance emri → yetim pozisyon, yanlış TP, kayıp `signal_source`

### Zorunlu giriş noktaları

| Olay | Metod |
|------|-------|
| Pozisyon açılış | `log_trade_open(..., signal_source=...)` |
| Pozisyon kapanış | `log_trade_close(..., close_reason=...)` |
| Savunma | `log_defense_triggered(...)` |
| Sync yetim | `sync_reality_from_binance()` + `detect_orphan_signal_source()` |
| Merter açılış | `merter_dca_manager._open_yuva()` |

### Tablolar

**`trades`** — Ana işlem defteri  
Alanlar: symbol, side, leverage, open/close time & price & qty, initial_margin, defense_triggered, weighted_avg_price, pnl_usdt, pnl_percent, roe_percent, close_reason, **signal_source**, status

**`signal_decisions`** — K2/K3 giyotin audit (scenario_label, k2_verdict, k3_action, …)

### Close reason standartları

`TP1`, `TP2`, `Trailing`, `Stop Loss`, `Hard Stop`, `Zaman stopu BE`, `Acil Tasfiye`, `Reconciliation (Binance kapalı)`

### Araçlar

- `scripts/sabah_kontrol.py`, `scripts/report_3coins.py`
- `journal.export_trades_csv()`, `journal.get_statistics()`
- Detay: `DERR_IMPLEMENTATION.md`

---

## 7. Sinyal Boru Hattı

```
Telegram mesajı
    │
    ├─[Haluk kanalı]──────────────────────────────────────────────┐
    │   listener.py                                                │
    │   → haluk_pdf_parser / signal_parser.parse_haluk_telegram    │
    │   → macro_levels_store (TOTAL, BTC.D, OTHERS, …)            │
    │   → raw_signal_queue.json (status: approved/rejected)        │
    │   → queue_watcher.py (signal_decisions audit)                │
    │   → signal_guillotine.evaluate_guillotine (Katman 2)         │
    │   → signal_guillotine.evaluate_katman3 (Katman 3)            │
    │   → signal_slot_bridge.try_fill_freed_slot / consume         │
    │   → mina_entry_orders (LIMIT vs MARKET)                      │
    │   → MinaPositionManager.log_position_open → DERR             │
    │   → main.py evaluate loop                                     │
    │                                                              │
    └─[Merter kanalı]─────────────────────────────────────────────┤
        listener.py → merter_dca_manager.handle_message()          │
            ├─ EI tarama → merter_ei_1 / merter_ei_2              │
            └─ RSI bot   → merter_other                            │
        (Legacy chat / $COIN Long → parser → kuyruk → motor hattı) │
```

### Katman özeti

| Katman | Bileşen | Görev |
|--------|---------|-------|
| 0 | `listener.py` | Telegram → kaynak ayrımı |
| 1 | `signal_parser.py` | Format parse, RVOL/RSI/EMA/SFP filtreleri |
| 2 | `signal_guillotine.py` | Seans, TOTAL yönü, SFP, parlaklık |
| 3 | `evaluate_katman3` | SKIP / PROCEED |
| 4 | `signal_slot_bridge.py` | Slot boşluğu, marjin cap, TTL |
| 5 | Motor / Merter DCA | Emir + izleme |

### Log dosyaları

| Dosya | İçerik |
|-------|--------|
| `mina_bot.log` | 4x motor aksiyonları |
| `signal_bot/signals_log.txt` | Listener olayları |
| `signal_bot/merter_dca.log` | DCA açılış/kapanış |
| `signal_bot/merter_dca_filter.log` | EI/RSI red nedenleri |
| `signal_bot/signal_filter.log` | Parser redleri |
| `raw_signal_queue.json` | Onaylı sinyal kuyruğu |

---

## 8. Dashboard Durumu

**Stack:** React (Vite) + WebSocket (`dashboard_ws.py`, port **8765**)  
**UI:** port **3000** (`mina-dashboard-vite.service`)

### Sekmeler / paneller

| Bileşen | Dosya | Durum |
|---------|-------|-------|
| Pozisyonlar (motor + Merter ayrı) | `PositionTable.jsx` | ✅ Merter yuva kartları |
| Savunma paneli | `DefensePanel.jsx` | ✅ D1/D2/D3 görsel |
| Makro seviyeler | `MacroLevelsPanel.jsx` | ✅ TOTAL, OTHERS, BTC.D, TOTAL3, … |
| Ayarlar | `SettingsPanel.jsx` | ✅ Merter zaman stopu, BE çarpanı, Telegram, motor toggle |
| Manuel Al/Sat | `OrderPanel.jsx` | ✅ Slot bar (7+1 motor, 3 Merter) |
| Mobil nav | `MobileNav.jsx` | ✅ Al/Sat · Pozisyonlar · Savunma · Log · Ayarlar |

### WebSocket veri

- Binance pozisyonlar, bakiye, slot özeti
- `defense_levels`, `tp_levels`, `initial_margins`
- Merter DCA state + RVOL cache
- `dashboard_settings.json` (canlı okuma/yazma)
- Motor pause: `motor_paused.flag`
- Log tail (`mina_bot.log`)

### Eksik (backlog)

- Merter parça doluluk göstergesi (3/10)
- Pozisyon kartında canlı RVOL
- DERR geçmiş grafikleri

---

## 9. Anayasa Kuralları Özeti

### Mutlak yasaklar

1. **Sabit USDT** kod içinde yazılmaz (20 USDT vb.)
2. **Savunma tetikleyicileri ROE değil spot fiyat**
3. **Pozisyon DERR'e yazılmadan açılmamalı/kapanmamalı**
4. **initial_margins.json** gerçek marjini yansıtmalı
5. **4x'te stop-loss yok** — savunma sistemi devrede

### TP (standard 1x–9x)

- TP1: ×1.03 → %50, sonra BE
- TP2: ×1.05 → %50
- Trailing: %2 callback (TP2 sonrası)

### TP (fast 10x)

- TP1: ×1.02 → %50
- TP2: ×1.04 → %100, trailing yok

### Stop-loss (4x hariç)

| Lev | SL% |
|-----|-----|
| 1x, 2x | 3 |
| 3x | 2 |
| 5x, 6x | 2 |
| 7x | 1.5 |
| 8x–10x | 1 |

### Testnet notu

`TRAILING_STOP_MARKET` ve conditional emirler **-4120** → engine-side trailing; `max_prices.json` seed zorunlu.

---

## 10. State / Tracking Dosyaları

| Dosya | Amaç |
|-------|------|
| `initial_margins.json` | Pozisyon başlangıç marjini |
| `initial_entry_prices.json` | Savunma referans girişi |
| `defense_levels.json` | D1/D2/D3 stage |
| `tp_levels.json` | TP1 yapıldı mı |
| `max_prices.json` | Trailing peak/trough |
| `position_sources.json` | HT/MZ/MANUEL/yetim |
| `pending_orders.json` | Bekleyen limit emirler |
| `position_states.json` | Motor runtime state |
| `raw_signal_queue.json` | Onaylı sinyal kuyruğu |
| `merter_dca_state.json` | Merter yuva durumu |
| `dashboard_settings.json` | UI ayarları |
| `engine.lock` | Motor PID |

Yönetim: `mina_tracking.py`

---

## 11. Önemli Dosya Rehberi

| Dosya | Rol |
|-------|-----|
| `main.py` | Motor giriş noktası |
| `mina_position_manager.py` | 4x karar + emir + DERR callback |
| `mina_trading_journal.py` | DERR SQLite |
| `mina_signal_source.py` | HT/MZ/yetim kaynak kodları |
| `mina_slot_policy.py` | 10 slot dağılımı |
| `mina_dashboard_settings.py` | Dashboard ayarları |
| `mina_entry_orders.py` | Limit/market + pending fill |
| `signal_bot/merter_dca_manager.py` | Merter 1x DCA çekirdek |
| `signal_bot/signal_slot_bridge.py` | Slot köprüsü |
| `signal_bot/signal_guillotine.py` | K2/K3 filtre |
| `signal_bot/listener.py` | Telegram |
| `backend/ghost_positions.py` | Hayalet tespiti |
| `backend/config.py` | Binance client |
| `dashboard/dashboard_ws.py` | WS sunucu |
| `scripts/deploy_full.py` | Prod deploy |

---

## 12. Operasyonel Notlar

### Deploy

```bash
python scripts/deploy_full.py
```

Servisleri restart eder; listener lock temizliği dahil.

### Hızlı kontrol

```bash
python scripts/sabah_kontrol.py
python scripts/report_3coins.py      # sunucuda
systemctl is-active mina-engine mina-merter-dca mina-listener
```

### Son operasyonel olaylar (2026-06-04/05)

- **MOVRUSDT:** Merter RSI DCA, DCA grid dolumu, trailing +16.6 USDT
- **ZROUSDT:** Merter EI → motor stop → yetim DCA limit dolumları → `signal_source=None` bug → düzeltildi
- **BTC SHORT #24:** TP1/TP2/trailing → slot boşaldı → eski kuyruk MZ sinyali → **BTC LONG #25**
- **ALGOUSDT:** Merter zaman stopu BE; motor yanlış stop_loss (1x çakışma)
- **ZRO DCA #9 limit:** Manuel iptal + motor kapanış iptali eklendi

---

## 13. AI Agent İçin Kurallar

1. **Anayasa önce:** `CLAUDE.md` / `MINA_ANAYASASI.md` ile çelişen kod yazma
2. **Minimal diff:** Sadece istenen görev; over-engineering yok
3. **DERR her zaman:** Açılış/kapanış/savunma journal'a
4. **Deploy sonrası:** Servis durumu + ilgili log kontrolü
5. **Sabit USDT yasak:** Tüm marjin slot/kasa formülünden
6. **Merter vs Motor:** 1x LONG Merter → motor müdahale etmez
7. **Commit:** Yalnızca kullanıcı isterse; push ayrı onay

---

*Bu belge MINA v2 operasyon ve geliştirme oturumlarından derlenmiştir. Güncelleme: yeni mimari karar veya kritik bug fix sonrası `GEMINI_BRIEFING.md` revize edilmelidir.*
