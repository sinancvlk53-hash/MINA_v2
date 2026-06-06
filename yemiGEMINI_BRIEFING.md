# MINA v2 — Yeni Gemini Briefing (Kapsamlı)

> **Dosya:** `yemiGEMINI_BRIEFING.md`  
> **Son güncelleme:** 2026-06-05  
> **Amaç:** Projeye yeni giren AI/agent için güncel tek kaynak: mimari, kararlar, bug fix geçmişi, backlog, operasyonel durum.  
> **Sunucu:** `178.105.150.40` · **Repo:** [sinancvlk53-hash/MINA_v2](https://github.com/sinancvlk53-hash/MINA_v2)  
> **Anayasa:** `CLAUDE.md`, `MINA_ANAYASASI.md`  
> **İlgili:** `SISTEM_ANALIZ_RAPORU.md`, `GEMINI_BRIEFING.md` (önceki sürüm)

---

## İçindekiler

1. [Proje özeti ve amacı](#1-proje-özeti-ve-amacı)
2. [Sistem mimarisi](#2-sistem-mimarisi)
3. [Slot dağılımı ve kasa kuralları](#3-slot-dağılımı-ve-kasa-kuralları)
4. [Düzeltilen kritik buglar](#4-düzeltilen-kritik-buglar)
5. [Mevcut açık sorunlar ve backlog](#5-mevcut-açık-sorunlar-ve-backlog)
6. [DERR sistemi](#6-derr-sistemi)
7. [Sinyal pipeline](#7-sinyal-pipeline)
8. [Dashboard durumu](#8-dashboard-durumu)
9. [Anayasa kuralları özeti](#9-anayasa-kuralları-özeti)
10. [Mevcut sistem durumu (2026-06-05)](#10-mevcut-sistem-durumu-2026-06-05)
11. [AI agent kuralları](#11-ai-agent-kuralları)

---

## 1. Proje özeti ve amacı

**MINA v2**, Binance Futures (şu an **Testnet**) üzerinde çalışan, çok kaynaklı Telegram sinyalleriyle güdümlenen otomatik trading sistemidir.

| Hedef | Açıklama |
|-------|----------|
| **Otomasyon** | Sinyal → filtre → pozisyon → TP / trailing / savunma → DERR |
| **Risk** | 10 slot dinamik kasa; 4x motor savunma (D1–D3); Merter 1x DCA ayrı hat |
| **Öz-denetim (DERR)** | SQLite journal — açılış/kapanış/savunma; DERR olmadan sistem kördür |
| **Gözetim** | React dashboard (:3000), WebSocket (:8765), manuel açılış, motor pause |

### İki ana trading hattı

| Hat | Slot | Giriş | Modül |
|-----|------|-------|-------|
| **4x Motor** | 8 (7 Haluk + 1 Merter legacy) | `main.py` / `MinaPositionManager` | TP, stop (4x hariç), D1–D3, engine trailing |
| **Merter 1x DCA** | 3 (2 EI + 1 RSI/diğer) | `merter_dca_manager.py` / `merter_dca_runner.py` | DCA grid, TP, trailing, 48s BE |

Eski monolit **`_archive/engine/main.py`** — canlıda **kullanılmaz**. Tek motor: **`main.py`**.

---

## 2. Sistem mimarisi

### 2.1 Bileşen haritası

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TELEGRAM: Haluk Hoca kanalı  │  Merter kanalı (EI / RSI / legacy chat)  │
└───────────────┬───────────────────────────────┬──────────────────────────┘
                │                               │
                ▼                               ▼
         listener.py (Katman 0)          listener.py
                │                               │
    haluk_pdf_parser + signal_parser            merter_dca_manager (1x)
                │                               │
                ▼                               ▼
      raw_signal_queue.json              merter_dca_runner (30s)
                │
    queue_watcher.py (2s audit)
                │
    signal_guillotine (K2/K3)
                │
    signal_slot_bridge.py (TTL 30dk, max 8 motor)
                │
                ▼
         main.py (30s) ──► MinaPositionManager ──► Binance Futures
                │                    │
                ▼                    ▼
    mina_trading_journal.db (DERR)   JSON tracking (mina_tracking.py)
                │
                ▼
    dashboard_ws.py (:8765, 5s) ──► React UI (:3000)
```

### 2.2 Systemd servisleri

| Servis | Script | Döngü | Görev |
|--------|--------|-------|-------|
| `mina-engine` | `main.py` | **30s** | 4x evaluate, sync, ghost, pending limit fill |
| `mina-merter-dca` | `merter_dca_runner.py` | **30s** + **5dk** reconcile | 1x DCA TP/trailing/BE |
| `mina-listener` | `signal_bot/listener.py` | event | Telegram Haluk + Merter |
| `mina-queue-watcher` | `queue_watcher.py` | **2s** | Pipeline audit, DERR karar logu |
| `mina-dashboard-ws` | `dashboard_ws.py` | **5s** broadcast | WS veri, manuel açılış subprocess |
| `mina-dashboard-vite` | `http.server :3000` | static | Dashboard UI |

Deploy: `scripts/deploy_full.py`

### 2.3 4x Motor (`MinaPositionManager`)

**Dosya:** `mina_position_manager.py`  
**Akış:** `evaluate_position()` → `execute_action()`

| Aksiyon | Tetik (LONG, spot) | Not |
|---------|-------------------|-----|
| **D1** | mark ≤ initial × 0.95 | +slot/5, TP devam, stop yok |
| **D2** | mark ≤ initial × 0.88 | +slot/5, TP dondur, BE emri |
| **D3** | 4H SFP + 5m bull bar | +slot×2/5 hayalet |
| **Hard Stop** | mark ≤ initial × 0.75 | Tam kapanış, 2s cooldown |
| **Stop Loss** | Kaldıraç bazlı % | **4x hariç** |
| **TP1** | giriş × 1.03 | %50 kapat, BE stop |
| **TP2** | giriş × 1.05 | %50 kapat |
| **Trailing** | `max_prices.json` engine-side | Testnet algo -4120 |

**Merter 1x istisna:** `ghost_positions.is_merter_dca_position()` → motor `hold`.

### 2.4 Savunma (4x only) — slot içi marjin

| Parça | Marjin | Tetik (LONG) |
|-------|--------|--------------|
| Giriş | slot / 5 | — |
| D1 | slot / 5 | initial × 0.95 |
| D2 | slot / 5 | initial × 0.88 |
| D3 | slot × 2/5 | Hayalet SFP |
| **Max risk / slot** | **500 USDT** (5000 kasa örneğinde) | Hard: × 0.75 |

**Kritik:** Tetikleyiciler **spot fiyat** — ROE sadece dashboard.

**State:** `defense_levels.json`, `initial_entry_prices.json`, `initial_margins.json`, `mina_position_state.json`

**Restart:** `sync_reality_from_binance()` defense + DERR `defense_triggered` korur.

### 2.5 Merter 1x DCA

**Modül:** `signal_bot/merter_dca_manager.py`  
**Yuvalar:** `merter_ei_1` (süzgeçli), `merter_ei_2` (süzgeçsiz), `merter_other` (RSI)

| Kural | Değer |
|-------|-------|
| Kaldıraç | 1x ISOLATED, stop yok |
| Parça | slot_budget / 10 (5000 kasa → 50 USDT/parça) |
| Giriş | 1× MARKET + 9× LIMIT (%2 adım) |
| EI | RVOL≥2, hacim≥50M, pump koruması, EMA20, SFP |
| RSI | RSI(5m)<20 + teyit |
| TP | +3% %50, +5% kalan, trailing %2 |
| Timeout | `merterTimeStopH` (4h) → breakeven modu |

**State:** `signal_bot/merter_dca_state.json`  
**Reconcile:** 5 dk `reconcile_state_from_derr()`

Detay: `MERTER_SIGNAL_FLOW.md`

### 2.6 Haluk PDF / Telegram

- **Parser:** `haluk_pdf_parser.py`, `signal_parser.py`
- PDF → macro seviyeler + coin sinyalleri → `raw_signal_queue.json`
- Makro panel: `macro_levels_store.py`
- Kaynak kodları: **HT**, **MZ**, **MANUEL**, **yetim**

---

## 3. Slot dağılımı ve kasa kuralları

**Politika:** `mina_slot_policy.py`

| Bölüm | Slot | Bütçe (5000 USDT örneği) |
|-------|------|--------------------------|
| Haluk 4x motor | 7 | 3500 USDT |
| Merter 4x legacy (köprü) | 1 | 500 USDT |
| **Motor toplam** | **8** | **4000 USDT** |
| Merter EI #1 (`merter_ei_1`) | 1 | 500 USDT → giriş **50 USDT** (slot/10) |
| Merter EI #2 (`merter_ei_2`) | 1 | 500 USDT → giriş **50 USDT** |
| Merter RSI (`merter_other`) | 1 | 500 USDT → giriş **50 USDT** |
| **Merter DCA toplam** | **3** | **1500 USDT** |
| **GENEL** | **10** | **5000 USDT** |

### Formüller (sabit USDT **YASAK**)

```
Kasa           = Binance futures USDT (dinamik)
1 Slot         = Kasa / 10
4x giriş marjini = Slot / 5          (%20)
4x hacim       = Marjin × Kaldıraç
Merter 1 parça = Slot / 10           (DCA yuvası içinde)
```

**4x örnek (500 USDT slot):** marjin 100 USDT, hacim 400 USDT (4x)

### Köprü / manuel limitleri

| Kontrol | Otomatik köprü | Manuel (`manual_open.py`) |
|---------|----------------|---------------------------|
| Max motor pozisyon | 8 (`MOTOR_SLOT_MAX`) | Haluk slot 7 + toplam 10 |
| Marjin tavanı %98 | Var | **Yok** (bilinen tutarsızlık) |
| Kuyruk TTL | 30 dk | — |
| Kaldıraç | Motor kuralları | **Whitelist: 1,2,3,4,5,10** |

---

## 4. Düzeltilen kritik buglar

| # | Sorun | Çözüm | Dosya / tarih |
|---|-------|-------|---------------|
| 1 | Dağınık eski `engine/main.py` | Tek çekirdek `main.py` + `MinaPositionManager` | `_archive/` |
| 2 | Restart defense sıfırlama | `sync_reality` preserve + DERR restore | `mina_position_manager.py` |
| 3 | D1 idempotency erken set → emir atılmadan `defense_levels=1` | `_execute_d1()` önce; persist sadece başarıda; journal `defense_triggered` kaynak | 2026-06-05 |
| 4 | Stale D1 marker (BTC) | `scripts/fix_stale_d1_markers.py` | 2026-06-05 |
| 5 | `-1109 Invalid account` (eski testnet key) | Yeni `.env` API key; bakiye okuma düzeldi | 2026-06-05 |
| 6 | Motor Merter 1x'e TP/stop | `is_merter_dca_position()` → hold | `ghost_positions.py` |
| 7 | Hayalet pozisyon spam | `scan_and_report()` | `ghost_positions.py` |
| 8 | Eski kuyruk sinyali saatler sonra (BTC LONG #25) | 30 dk queue TTL | `signal_slot_bridge.py` |
| 9 | Merter state kaybı | 5 dk `reconcile_state_from_derr()` | `merter_dca_runner.py` |
| 10 | Motor kapanışta orphan DCA limit (ZRO) | `_cancel_merter_dca_limits()` | `mina_position_manager.py` |
| 11 | Yetim `signal_source=None` | `detect_orphan_signal_source()` → MZ / yetim | `mina_signal_source.py` |
| 12 | Testnet trailing -4120 | Engine-side trailing + `max_prices` seed | `check_trailing_stop()` |
| 13 | DERR `signal_source` eksik | Kolon + Merter/MANUEL yazımı | `mina_trading_journal.py` |
| 14 | Kısmi TP sonrası DERR qty eski | `reconcile_open_qty()` + script | 2026-06-05 |
| 15 | ATOM tracking eksik (Merter ei_2) | `reconcile_atom_derr.py` seed | 2026-06-05 |
| 16 | `signal_slot_bridge` syntax (`score_entry`) | Duplicate `_open_position_keys` düzeltildi | 2026-06-05 |
| 17 | Manuel açılış 6–9x kaldıraç | Whitelist `[1,2,3,4,5,10]` CLI + WS | 2026-06-05 |
| 18 | Yeni testnet temiz başlangıç | JSON state sıfırlandı; 6 MANUEL pozisyon test | 2026-06-05 |

---

## 5. Mevcut açık sorunlar ve backlog

### 🟡 Bilinen tutarsızlıklar (kodda)

| Konu | Durum |
|------|-------|
| Manuel vs köprü slot sayımı | Manuel: 7 haluk + 10 total; köprü: 8 motor + marjin cap |
| Manuel `--source merter` | Sayım hatası, pratikte kullanılmaz |
| D1 hata logları | `_execute_d1` `print()` — `mina_bot.log`'da görünmeyebilir |
| Dashboard OrderPanel "Stop" emir tipi | UI'da var, backend'de yok |
| DERR eski kayıtlar `signal_source=null` | 20 kayıt; istatistikleri kirletir |
| Kısmi TP → DERR qty | `reconcile_open_qty` var; otomatik değil, motor loop'ta yok |

### 🟡 Backlog (`MINA_ANAYASASI.md`)

- [ ] D1/D2 sabit % vs dinamik — **50 işlem DERR analizi** sonrası
- [ ] RSI > 70 → LONG reddet (Merter)
- [ ] Fiyat EMA20 altında → LONG reddet (Merter)
- [ ] 4H SFP dinamik destek (20–50 mum dip fitili)
- [ ] Dashboard: Merter parça doluluk (3/10), canlı RVOL kartı
- [ ] Trailing algo endpoint gerçek hesap testi
- [ ] D3 öncesi bakiye yeniden hesaplama
- [ ] Order retry mekanizması
- [ ] Global risk limiti
- [ ] Backtest prod entegrasyonu
- [ ] Hetzner Frankfurt prod sunucu

### 🟢 Gerçek hesap öncesi checklist

- [ ] `/fapi/v1/order/algo/trailing` test
- [ ] D3 öncesi bakiye recalc
- [ ] Order retry
- [ ] Slot limit edge case'leri
- [ ] Merter/Motor aynı sembol çakışması
- [ ] Her açılış/kapanış DERR zorunlu
- [ ] `max_prices.json` restart seed

### Testnet kısıtları

- `TRAILING_STOP_MARKET` / conditional → **-4120**
- Çözüm: engine-side trailing; `max_prices.json` seed **zorunlu**

---

## 6. DERR sistemi

**DERR** = Veri Tabanlı Öz-Denetim ve İşlem Günlüğü  
**Dosya:** `mina_trading_journal.py` → `mina_trading_journal.db`

### Neden kritik?

> *"DERR sistemin hafızasıdır. Burası olmadan sistem kördür."*

- Sync, rapor, Merter reconcile, dashboard PnL → DERR
- DERR dışı emir → yetim pozisyon, yanlış TP, kayıp `signal_source`

### Zorunlu giriş noktaları

| Olay | Metod |
|------|-------|
| Açılış | `log_trade_open(..., signal_source=...)` |
| Kapanış | `log_trade_close(..., close_reason=...)` |
| Savunma | `log_defense_triggered(...)` |
| Kısmi TP qty güncelle | `reconcile_open_qty(trade_id, qty, margin)` |
| Sync yetim | `sync_reality_from_binance()` + `detect_orphan_signal_source()` |
| Merter açılış | `merter_dca_manager` → DERR `merter_ei_*` / `merter_other` |

### `trades` tablosu (özet)

symbol, side, leverage, open/close time & price & qty, initial_margin, defense_triggered, weighted_avg_price, pnl_usdt, roe_percent, close_reason, **signal_source**, status

### Close reason örnekleri

`TP1`, `TP2`, `Trailing`, `Stop Loss`, `Hard Stop`, `Zaman stopu BE`, `Reconciliation (Binance kapalı)`, `Trailing/Reconcile`

### Kaynak kodları

| Kod | Anlam |
|-----|-------|
| HT | Haluk Hoca pipeline |
| MZ | Merter (motor/kuyruk) |
| MANUEL | Dashboard / `manual_open.py` |
| merter_ei_1 / merter_ei_2 / merter_other | Merter DCA yuvası |
| yetim | Orphan sync, kaynak bilinmiyor |

### DERR istatistikleri (2026-06-05, testnet)

| Metrik | Değer |
|--------|-------|
| Toplam kayıt | 35 |
| Kapalı | 31 |
| Realized PnL | **-312.15 USDT** (çoğu eski reconcile) |
| Win rate | 45.16% |
| En iyi | MOVR +16.63 (Trailing) |
| En kötü | LAB -224.57 (Reconcile) |

Detay: `DERR_IMPLEMENTATION.md`, `scripts/derr_stats_export.py`

---

## 7. Sinyal pipeline

```
Telegram
  │
  ├─[Haluk]─────────────────────────────────────────────┐
  │  listener.py                                         │
  │  → parse_haluk_telegram / haluk_pdf_parser           │
  │  → macro_levels_store                                │
  │  → raw_signal_queue.json (approved/rejected)         │
  │  → queue_watcher (audit, 2s)                         │
  │  → signal_guillotine K2 (TOTAL, seans, SFP, parlaklık)│
  │  → evaluate_katman3 K3 (SKIP / PROCEED)              │
  │  → signal_slot_bridge (slot, TTL 30dk, max 8)        │
  │  → MARKET/LIMIT → tracking seed → DERR               │
  │  → main.py evaluate (30s)                            │
  │                                                      │
  └─[Merter]─────────────────────────────────────────────┤
      listener → merter_dca_manager                        │
        ├─ EI → merter_ei_1 / merter_ei_2                 │
        └─ RSI → merter_other                             │
      (Legacy chat → parser → kuyruk → motor hattı)       │
```

### Katman özeti

| Katman | Bileşen | Red nedeni örnekleri |
|--------|---------|---------------------|
| 0 | `listener.py` | Duplicate PID, config eksik |
| 1 | `signal_parser.py` | NEWS_ALARM, makro-only, RVOL/RSI fail |
| 2 | `signal_guillotine.py` | TOTAL↓ + Merter LONG (F1) |
| 3 | `evaluate_katman3` | REJECT → SKIP |
| 4 | `signal_slot_bridge.py` | MAX 8, MARGIN_CAP, TTL, duplicate key |
| 5 | Motor / Merter DCA | Binance API, motor pause |

### Log dosyaları

| Dosya | İçerik |
|-------|--------|
| `mina_bot.log` | Motor TP/defans/trailing |
| `signal_bot/signals_log.txt` | Listener |
| `signal_bot/merter_dca.log` | DCA |
| `signal_bot/pipeline_audit.log` | Queue watcher |
| `raw_signal_queue.json` | Onaylı kuyruk |

---

## 8. Dashboard durumu

**Stack:** React (Vite) + `dashboard_ws.py` (:8765) → UI (:3000)

### Paneller

| Bileşen | Durum |
|---------|-------|
| `PositionTable.jsx` | Motor + Merter ayrı, signal source, RVOL |
| `DefensePanel.jsx` | D1/D2/D3 |
| `MacroLevelsPanel.jsx` | TOTAL, BTC.D, OTHERS, … |
| `SettingsPanel.jsx` | Motor toggle, Merter/Haluk zaman stopu, Telegram |
| `OrderPanel.jsx` | Manuel açılış, slot bar 7+3, kaldıraç 1–5/10 |
| `MobileNav.jsx` | Mobil sekme |

### Manuel açılış (`OrderPanel` → WS → `manual_open.py`)

- Coin, LONG/SHORT, kaldıraç **1,2,3,4,5,10**
- Limit fiyat (opsiyonel) → LIMIT veya MARKET
- Marjin: **slot/5 otomatik** (miktar kutusu kaldırıldı)
- DERR: **MANUEL**
- Motor pause → reddeder

### WS veri (5s)

Bakiye, pozisyonlar, slot özeti, defense/tp levels, Merter state, settings, log tail

### Backlog (dashboard)

- Merter parça doluluk (3/10)
- DERR geçmiş grafikleri

---

## 9. Anayasa kuralları özeti

### Mutlak yasaklar

1. **Sabit USDT** kod içinde yazılmaz
2. **Savunma tetikleyicileri ROE değil spot fiyat**
3. **Pozisyon DERR'e yazılmadan açılmamalı/kapanmamalı**
4. **`initial_margins.json`** gerçek marjini yansıtmalı
5. **4x'te stop-loss yok** — savunma devrede

### TP (standard 1x–9x)

- TP1: ×1.03 → %50, BE stop
- TP2: ×1.05 → %50
- Trailing: %2 callback (engine-side testnet)

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

---

## 10. Mevcut sistem durumu (2026-06-05)

### Ortam

- **Testnet** — yeni hesap ~5000 USDT
- API `-1109` sorunu giderildi (yeni key)
- JSON tracking temiz başlangıç + MANUEL test pozisyonları

### Açık pozisyonlar (örnek anlık snapshot ~21:06 UTC)

| Sembol | Yön | Lev | Not |
|--------|-----|-----|-----|
| SOLUSDT | LONG | 4x | MANUEL test |
| LINKUSDT | LONG | 4x | MANUEL test |
| INJUSDT | LONG | 4x | TP1 tetiklendi |
| ATOMUSDT | LONG | 1x | Merter ei_2 DCA |

**Kapanan (bugün):** XRP/ADA/DOT SHORT trailing; eski hesap reconcile kayıtları

### Tracking uyumu

Binance ↔ DERR ↔ JSON **TAM UYUMLU** (reconcile sonrası, 6 pozisyon dönemi)

### Önemli state dosyaları

| Dosya | Amaç |
|-------|------|
| `initial_entry_prices.json` | Savunma referans giriş |
| `initial_margins.json` | Başlangıç marjini |
| `defense_levels.json` | D stage |
| `tp_levels.json` | TP1/TP2 durumu |
| `max_prices.json` | Trailing peak/trough |
| `position_sources.json` | HT/MZ/MANUEL |
| `mina_position_state.json` | tp1_done, defense_stage, … |
| `merter_dca_state.json` | Merter yuvaları |
| `pending_orders.json` | Bekleyen manuel limit |
| `engine.lock` | Motor PID |

Yönetim: `mina_tracking.py`

### Son git commit'ler (referans)

- `docs: sistem analiz raporu`
- `feat: kaldıraç whitelist 1,2,3,4,5,10 - manuel açılış düzeltmeleri`
- `fix: ATOM tracking seed, SHORT qty reconcile, yeni testnet temiz başlangıç`

---

## 11. AI agent kuralları

1. **Anayasa önce:** `CLAUDE.md` / `MINA_ANAYASASI.md` ile çelişme
2. **Minimal diff:** Sadece istenen görev
3. **DERR her zaman:** Açılış/kapanış/savunma journal'a
4. **Deploy sonrası:** Servis + log kontrolü
5. **Sabit USDT yasak:** Slot/kasa formülü
6. **Merter vs Motor:** 1x Merter DCA tracked → motor müdahale etmez
7. **Commit/push:** Yalnızca kullanıcı isterse
8. **Testnet:** Algo trailing kullanma; engine trailing + max_prices seed

### Hızlı operasyon

```bash
python scripts/deploy_full.py
python scripts/sabah_kontrol.py
python scripts/instant_report.py          # sunucuda
systemctl is-active mina-engine mina-merter-dca mina-listener
```

### Önemli dosyalar

| Dosya | Rol |
|-------|-----|
| `main.py` | Motor giriş |
| `mina_position_manager.py` | 4x karar + emir |
| `mina_trading_journal.py` | DERR |
| `scripts/manual_open.py` | Manuel açılış |
| `signal_bot/signal_slot_bridge.py` | Slot köprüsü |
| `signal_bot/merter_dca_manager.py` | Merter DCA |
| `dashboard/dashboard_ws.py` | WS + manuel subprocess |
| `scripts/deploy_full.py` | Deploy |

---

*Bu belge 2026-06-05 oturumlarındaki mimari kararlar, bug fix'ler ve operasyonel durumdan derlenmiştir. Güncelleme: kritik değişiklik sonrası `yemiGEMINI_BRIEFING.md` revize edilmelidir.*
