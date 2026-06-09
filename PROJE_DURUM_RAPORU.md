# MINA v2 — Proje Durum Raporu

> **Tarih:** 8 Haziran 2026  
> **Son commit (main):** `ee86395` — *feat: dashboard makro/favori panel + D2 fiyat fix + kill-switch banner*  
> **Release tag:** `v1.0-savunma-calisiyor`  
> **Sunucu:** `178.105.150.40` (testnet)  
> **Repo:** [sinancvlk53-hash/MINA_v2](https://github.com/sinancvlk53-hash/MINA_v2)

---

## Özet

MINA v2 testnette **üretim modunda** çalışıyor. 4x motor savunma sistemi (D1/D2) doğrulandı; Merter 1x DCA, dashboard, DERR journal ve operasyonel güvenlik katmanları aktif. Bugün makro izleme servisi kodlandı (henüz commit/deploy edilmedi) ve eski systemd unit'ler temizlendi. Gerçek hesap geçişi ve makro filtrenin motora bağlanması plan aşamasında.

---

## ✅ Tamamlandı ve Çalışıyor

### Çekirdek motor (4x Haluk pipeline)

| Bileşen | Durum |
|---------|-------|
| Tek motor mimarisi (`main.py` + `MinaPositionManager`) | ✅ |
| TP1/TP2 + engine-side trailing (`max_prices.json`) | ✅ |
| Savunma D1 (`×0.95`) / D2 (`×0.88`) | ✅ testnet doğrulandı |
| D1 idempotency v2 (restart/zombie koruması) | ✅ |
| Hard stop (`×0.75`) + 2 saat coin cooldown | ✅ |
| Kill-switch (%20 günlük zarar → yeni giriş blok) | ✅ |
| Order retry + rate limit koruması | ✅ |
| DERR journal (`mina_trading_journal.db`) | ✅ |

### Sinyal hattı

| Bileşen | Durum |
|---------|-------|
| Telegram listener + K2/K3 giyotin + slot köprüsü (30 dk TTL) | ✅ |
| Haluk PDF/Telegram parser + makro seviye kaydı | ✅ |
| RSI > 70 LONG reddi | ✅ |
| Merter 1x DCA (3 yuva: EI×2 + RSI) | ✅ |

### Dashboard

| Bileşen | Durum |
|---------|-------|
| React UI (port 3000) + WebSocket (8765) | ✅ |
| Savunma paneli, manuel TP/stop override | ✅ |
| Favori coinler, PnL → pozisyon overlay | ✅ |
| Makro sekmesi (Haluk seviyeleri + funding) | ✅ |
| Şifre koruması, mobil nav | ✅ |

### Sunucu servisleri (8 Haziran 2026)

```
mina-engine          active
mina-listener        active
mina-merter-dca      active
mina-queue-watcher   active
mina-dashboard-ws    active
mina-dashboard-vite  active
mina-haluk-yayin     active
mina-upbit-listings  active
mina-binance-listings active
```

---

## ⚠️ Yapıldı Ama Aktif Değil / Yarım

| Özellik | Durum | Not |
|---------|-------|-----|
| **Makro izleyici** (`mina_makro_watcher.py`) | Kod hazır, **commit/deploy bekliyor** | Lokal state çalışıyor; sunucuda servis `inactive` |
| **Haluk yayın özeti** (`haluk_broadcast_summary.py`) | Pipeline'a bağlı değil | Sadece tahmin hatırlatıcı (`mina-haluk-yayin`) aktif |
| **Copy trading** | Altyapı var, pasif | Sunucuda `FOLLOWER_*` env tanımlı değil |
| **Backtest** | Scriptler var, son çalıştırma 31 Mayıs | Otomasyon/cron yok |
| **Upbit listing trader** | Watcher aktif, trader state boş | Kod hazır, pozisyon açmıyor |
| **Makro rejim filtresi (motora bağlı)** | Planlandı | İşlem izni şimdilik sadece gösterim — motoru etkilemiyor |
| **D3 SFP** | Kod var, basitleştirilmiş | 3 temas kuralı tam değil |
| **Trailing algo endpoint** | Test edilmedi | Canlı geçiş öncesi zorunlu |
| **Testnet conditional emirler** | D2 breakeven -4120 riski | Canlıda doğrulanmadı |
| **Dashboard backlog** | Merter parça doluluk (3/10), canlı RVOL kartı | Eksik |

### Bugünkü operasyonel işlemler

- **Eski systemd unit temizliği:** `mina-ht-listener`, `mina-merter`, `mina-pdf-listener` silindi (hepsi inactive veya crash-loop'taydı)
- **Leverage kuralları canlı testi:** ZEC/MYX D1/D2 ✅; FHE D2 `-4024` tickSize bug → `_round_price()` fix ✅
- **Kill-switch banner:** Stale `daily_risk_state` düzeltmesi ✅
- **BCH journal PnL reset:** Testnet günlük zarar kill-switch temizlendi ✅

### Commit edilmemiş yerel değişiklikler

```
M  dashboard/dashboard_ws.py
M  dashboard/src/App.jsx, App.css
M  dashboard/dist/*
M  requirements.txt
M  scripts/deploy_full.py
?? mina_makro_core.py
?? mina_makro_watcher.py
?? ops/mina-makro-watcher.service
?? dashboard/src/components/MacroWatcherPanel.jsx
?? signal_bot/makro_watcher_state.json
?? scripts/_fhe_*.py, leverage_rules_test.py  (geçici test scriptleri)
```

---

## ❌ Planlandı Ama Yapılmadı

| Madde | Kaynak |
|-------|--------|
| Gerçek hesaba geçiş (`BINANCE_TESTNET=false`) | `GERCEK_HESAP_GECIS.md` — tüm checklist açık |
| Hetzner Frankfurt prod sunucu | `GUNCEL_NOTLAR.md` |
| Makro filtrenin sinyal katmanına bağlanması | `MAKRO_STRATEJI_NOTLARI.md` |
| ETF akışı, likidasyon haritası, order flow | Makro Öncelik 2–3 |
| 4H SFP dinamik destek algoritması | `MINA_ANAYASASI.md` backlog |
| EMA20 LONG reddi (genel) | Backlog |
| D1/D2 dinamik eşik (50 işlem DERR analizi) | Anayasa önkoşulu |
| HTTPS dashboard + sunucu monitoring | `GERCEK_HESAP_GECIS.md` |
| 50 temiz DERR işlemi + expectancy analizi | ~33 kayıt var, çoğu legacy |
| Haluk video otomatik transkript → özet pipeline | Scriptler var, tam otomasyon yok |

---

## Makro İzleyici (Yeni — 8 Haziran)

**Dosyalar:** `mina_makro_watcher.py`, `mina_makro_core.py`, `ops/mina-makro-watcher.service`, `dashboard/src/components/MacroWatcherPanel.jsx`

**Veri kaynakları:** Binance Futures (fiyat, funding, OI, L/S), CoinGecko (TOTAL, dominance, OTHERS), Alternative.me (Fear & Greed), yfinance (DXY, USOIL, SPX), Binance XAUUSDT

**Döngü:** 15 dakika

**Çıktılar:**
- Tekil alarmlar (cooldown'lı, birleştirilmiş Telegram)
- Kombinasyon analizi (altcoin sezonu, risk-off vb.)
- Risk Skoru (0–6) + Macro Skor (-100/+100)
- İşlem izni önerisi: 🟢 FULL / 🟡 REDUCED / 🔴 DEFENSIVE *(motoru etkilemiyor)*
- Sabah 08:00 TR tam özet (Telegram)

**Son lokal snapshot (18:26 TR):**

| Metrik | Değer |
|--------|-------|
| TOTAL | 2.284T (+2.8%) |
| BTC | $64,070 (+3.6%) |
| BTC.D | 56.28% |
| Fear & Greed | 8 (Extreme Fear) |
| Risk Skoru | 1/6 |
| Macro Skor | +8 |
| İşlem İzni | 🟡 REDUCED RISK |

Tüm kaynaklar `ok`. **Deploy + commit bekliyor.**

---

## Son Commit'ler (özet)

| Commit | Açıklama |
|--------|----------|
| `ee86395` | Dashboard makro/favori panel, D2 tickSize fix, kill-switch banner |
| `81b4a46` | GEMINI_BRIEFING güncellendi |
| `f79aa88` | SABAH_KONTROL.md eklendi |
| `12a092a` | D1 idempotency v2 + zombie process fix |
| `06a32a2` | haluk_predictions WAL fix |
| `0c03b67` | Denetim düzeltmeleri + 67 script `_archive`'a |
| `fad6d20` | Güvenlik, retry, global risk, D2 zaman stopu |
| `0ad36f5` | Merter 1x DCA tamamlandı |
| `bb06175` | Tek motor mimarisi, DERR aktif |

---

## Kritik Açık Riskler

1. **Canlı conditional emirler test edilmedi** — D2/D3 breakeven testnette -4120 alabilir
2. **Algo trailing endpoint** — `/fapi/v1/order/algo/trailing` hiç denenmedi
3. **Makro skor ağırlıkları** — backtest ile kalibre edilmedi (şimdilik sabit)
4. **Zombie process riski** — `SABAH_KONTROL.md` ile günlük kontrol gerekli
5. **Temiz DERR verisi yetersiz** — gerçek hesap kararı için 50 temiz motor işlemi hedefi

---

## Öncelik Sırası (Öneri)

1. Makro izleyici commit + deploy + servis doğrulama
2. Dashboard `MacroWatcherPanel` build + sunucuya dist deploy
3. Canlı D2/D3 conditional emir testi (küçük pozisyon)
4. Makro skorları 2–4 hafta gözlem → sonra motora bağlama kararı
5. Gerçek hesap geçiş checklist (`GERCEK_HESAP_GECIS.md`)

---

## Dokümantasyon Haritası

| Dosya | İçerik |
|-------|--------|
| `CLAUDE.md` | Motor anayasası özeti |
| `MINA_ANAYASASI.md` | Tam kurallar + backlog |
| `GEMINI_BRIEFING.md` | AI agent briefing (mimari, buglar, operasyon) |
| `GERCEK_HESAP_GECIS.md` | Canlı geçiş checklist |
| `MAKRO_STRATEJI_NOTLARI.md` | Makro rejim roadmap |
| `SABAH_KONTROL.md` | Günlük operasyon komutları |
| `PROJE_DURUM_RAPORU.md` | Bu dosya |

---

*Rapor oluşturulma: 8 Haziran 2026. Sonraki güncelleme: deploy/commit veya major milestone sonrası.*
