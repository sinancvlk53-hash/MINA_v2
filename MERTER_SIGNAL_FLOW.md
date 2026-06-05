# Merter Sinyal Akışı — Süzgeç Raporu

Merter Telegram kanalından gelen bir sinyalin MINA'da işleme dönüşene kadar geçtiği adımlar.

---

## A) EI Tarama Botu (`Yeni AL Sinyalleri` / `Sinyal Taraması`)

**Giriş:** `signal_bot/listener.py` → `merter_dca_manager.handle_message()`

Listener önce DCA manager'a devreder; mesaj EI formatındaysa aşağıdaki iki yuva **bağımsız** değerlendirilir.

### Yuva 1 — `merter_ei_1` (Süzgeçli)

| # | Adım | Kontrol | Reddetme |
|---|------|---------|----------|
| 1 | Mesaj formatı | `Yeni AL Sinyalleri` veya `Sinyal Taraması` | Mesaj EI değilse DCA dışı |
| 2 | Yuva doluluğu | `merter_ei_1` boş mu? | Dolu → atla |
| 3 | Coin listesi | Regex ile USDT sembolleri çıkar | Liste boş → aday yok |
| 4 | **RVOL** | Son 5m hacim / 1s ort. ≥ **2.0** | RVOL düşük → coin elenir |
| 5 | **24s hacim** | Futures quote hacmi ≥ **50M USD** | Düşük hacim → elenir |
| 6 | **Pump koruması** | Son 15 dk fiyat artışı < **%5** | Pump var → sıradaki coin |
| 7 | **EMA20** | Mark fiyat > EMA20 (LONG) | Altında → elenir |
| 8 | **Destek/direnç** | Fiyat S/R bölgesinde (ATR toleransı) | Boşlukta → elenir |
| 9 | **SFP / Pin / Engulfing** | Son 15m mumda pattern | Yok → elenir |
| 10 | Sıralama | RVOL en yüksek geçen coin | Hiç geçen yok → yuva açılmaz |
| 11 | Çift teyit | Aynı coin diğer yuvada 15 dk içinde? | Varsa 2 parça ile giriş |
| 12 | Emir | MARKET 1x ISOLATED + 9 DCA limit | Binance / marjin hatası |

### Yuva 2 — `merter_ei_2` (Süzgeçsiz)

| # | Adım | Kontrol | Reddetme |
|---|------|---------|----------|
| 1 | Mesaj formatı | EI tarama mesajı | Aynı |
| 2 | Yuva doluluğu | `merter_ei_2` boş mu? | Dolu → atla |
| 3 | Coin seçimi | Listedeki **ilk** LONG coin | Liste boş → açılmaz |
| 4 | Filtre | **Yok** (RVOL, EMA, SFP, hacim, pump kontrol edilmez) | — |
| 5 | Çift teyit | 15 dk içinde aynı coin başka yuvada? | 2 parça giriş |
| 6 | Emir | MARKET 1x + DCA limitleri | Hata |

---

## B) RSI Bot (`RSI Analizi`)

**Yuva:** `merter_other`

| # | Adım | Kontrol | Reddetme |
|---|------|---------|----------|
| 1 | Format | `RSI Analizi` bölümü | Yoksa atlanır |
| 2 | RSI(5m) | `< 20` (LONG) | ≥ 20 → red |
| 3 | RSI teyit | 1–2 mumda +3 puan veya 20 kırılımı | Teyit yok → red |
| 4 | 24s hacim | ≥ 50M USD | Düşük → red |
| 5 | Yuva | `merter_other` boş | Dolu → red |
| 6 | Emir | MARKET 1x + DCA | Hata |

---

## C) Legacy / Sohbet Merter (4x Motor Kuyruğu)

**Giriş:** `signal_parser.parse_merter()` → `raw_signal_queue.json`

Bu yol **Merter DCA değil**, Haluk motor slot köprüsüne gider.

| # | Katman | Süzgeç | Reddetme |
|---|--------|--------|----------|
| 1 | Parser | Legacy chat / `$COIN için Long` formatı | Tanınmazsa kayıt yok |
| 2 | EI bot parser | `_parse_ei_trading_bot` → EMA20+SFP+S/R | Filtre geçmezse kuyruğa girmez |
| 3 | RSI bot parser | `_parse_rsi_bot` → RSI+SFP | Filtre geçmezse girmez |
| 4 | Kuyruk | `status: approved` | rejected → bridge almaz |
| 5 | **Katman 2 Giyotin** | `evaluate_guillotine` — seans, TOTAL yönü, SFP, parlaklık | REJECT |
| 6 | **Katman 3** | `evaluate_katman3` — eylem SKIP | SKIP |
| 7 | Slot bridge | Açık pozisyon / MAX 8 motor / marjin cap | Red |
| 8 | Giriş emri | `entry_price < mark` → LIMIT, aksi MARKET | Emir hatası |
| 9 | Motor | 4x ISOLATED, D1/D2/D3, TP, trailing | — |

---

## D) Paralel Servisler

| Servis | Rol |
|--------|-----|
| `mina-listener.service` | Telegram → listener → DCA / parser |
| `mina-merter-dca.service` | Açık DCA pozisyon TP/trailing/48s izleme |
| `mina-engine.service` | 4x motor + pending limit fill + slot bridge |
| `queue_watcher.py` | Merter `approved` → `signal_decisions` log (motor açmaz) |

---

## E) Log Dosyaları

| Dosya | İçerik |
|-------|--------|
| `signal_bot/merter_dca.log` | DCA açılış / kapanış |
| `signal_bot/merter_dca_filter.log` | EI/RSI red nedenleri |
| `signal_bot/signal_filter.log` | Parser EMA/SFP redleri (motor kuyruğu) |
| `signal_decisions.json` | K2/K3 kararları |

---

## Özet

- **DCA (1x):** Listener → `merter_dca_manager` — iki EI yuvası farklı süzgeçle, RSI ayrı yuva.
- **Motor (4x):** Parser → giyotin → slot bridge — Haluk PDF/Merter legacy onaylı sinyaller.
- **merter_ei_1:** Tam süzgeç (RVOL + hacim + pump + EMA20 + S/R + SFP).
- **merter_ei_2:** Sıfır süzgeç — listedeki ilk coin direkt açılır.
