# MINA v2 — Sunucu Kurtarma Prosedürü

Sunucu bozulursa veya yeni makineye taşınacaksa bu adımları sırayla uygula.
Hedef süre: **~30–45 dakika** (yedek mevcut, DNS/API key hazır).

---

## Ön koşullar

- SSH erişimi (root veya sudo)
- GitHub repo: `sinancvlk53-hash/MINA_v2`
- `.env` yedeği (Google Drive / şifreli not) — **repo'ya koyma**
- Son yedek: `/root/backups/MINA_v2_YYYYMMDD_HHMMSS.tar.gz`

---

## Adım 1 — Sunucuya eriş ve temel paketler (5 dk)

```bash
ssh root@178.105.150.40
apt update && apt install -y python3 python3-venv python3-pip git cron logrotate
mkdir -p /root/backups
```

---

## Adım 2 — Kodu geri yükle (5 dk)

**Seçenek A — GitHub'dan (tercih):**

```bash
cd /root
git clone https://github.com/sinancvlk53-hash/MINA_v2.git
cd MINA_v2
git checkout main
```

**Seçenek B — Son yedekten:**

```bash
cd /root
tar -xzf /root/backups/MINA_v2_ENSON.tar.gz
cd MINA_v2
git pull origin main   # mümkünse güncel commit'e çek
```

---

## Adım 3 — Python ortamı (5 dk)

```bash
cd /root/MINA_v2
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/pip install pymupdf pdfplumber websockets psutil
```

---

## Adım 4 — `.env` ve gizli dosyalar (3 dk)

```bash
# Yedekten .env'i geri koy (ASLA GitHub'a commit etme)
nano /root/MINA_v2/.env
# BINANCE_TESTNET, API keys, TELEGRAM, ANTHROPIC_API_KEY, MINA_SSH_PASS vb.

# Telegram session dosyaları varsa yedekten kopyala:
# session.session, session_ht.session
```

Kontrol:

```bash
grep -E 'BINANCE|ANTHROPIC|TELEGRAM' /root/MINA_v2/.env | sed 's/=.*/=***/'
```

---

## Adım 5 — Veri dosyalarını geri yükle (5 dk)

Yedekten veya eski sunucudan kopyala:

| Dosya | Açıklama |
|-------|----------|
| `mina_trading_journal.db` | DERR |
| `initial_entry_prices.json` | Motor tracking |
| `initial_margins.json` | Marjin |
| `defense_levels.json` | Savunma |
| `signal_bot/merter_dca_state.json` | Merter state |
| `signal_bot/macro_levels.json` | Makro panel |
| `signal_bot/raw_signal_queue.json` | Sinyal kuyruğu |

---

## Adım 6 — Systemd servisleri (5 dk)

Servis dosyalarını kur:

```bash
cp /root/MINA_v2/ops/mina-dashboard-ws.service /etc/systemd/system/
# Diğer servisler zaten /etc/systemd/system/ altındaysa atla
systemctl daemon-reload
systemctl enable mina-engine mina-listener mina-merter-dca mina-queue-watcher mina-dashboard-ws mina-dashboard-vite
systemctl restart mina-engine mina-listener mina-merter-dca mina-queue-watcher mina-dashboard-ws mina-dashboard-vite
```

Doğrula:

```bash
systemctl is-active mina-engine mina-listener mina-merter-dca mina-dashboard-ws mina-dashboard-vite
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
```

---

## Adım 7 — Cron yedek + logrotate (2 dk)

```bash
chmod +x /root/MINA_v2/ops/backup_mina.sh
(crontab -l 2>/dev/null | grep -v backup_mina; echo '0 2 * * * /root/MINA_v2/ops/backup_mina.sh >> /root/backups/backup.log 2>&1') | crontab -
cp /root/MINA_v2/ops/logrotate_mina /etc/logrotate.d/mina
sed -i 's/\r$//' /etc/logrotate.d/mina
crontab -l | grep backup_mina
```

---

## Adım 8 — Canlı doğrulama (5–10 dk)

```bash
cd /root/MINA_v2
venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import os; print('ANTHROPIC', bool(os.getenv('ANTHROPIC_API_KEY')))"

# Makro WS
venv/bin/python scripts/ws_macro_sniff.py   # macroLevels gelmeli

# PDF görsel parser (son PDF)
ls -t signal_bot/pdfs/*.pdf | head -1
venv/bin/python signal_bot/haluk_pdf_parser.py signal_bot/pdfs/EN_SON.pdf

# Motor log
tail -20 mina_bot.log
```

Dashboard: `http://178.105.150.40:3000` — pozisyonlar, makro panel, log akışı.

---

## Adım 9 — Gerçek hesap öncesi son kontrol

[`GERCEK_HESAP_GECIS.md`](GERCEK_HESAP_GECIS.md) listesindeki tüm maddeleri işaretle.

---

## Hızlı referans — servisler

| Servis | Rol |
|--------|-----|
| `mina-engine` | Ana motor (`main.py`) |
| `mina-listener` | Telegram dinleyici |
| `mina-merter-dca` | Merter DCA |
| `mina-queue-watcher` | Sinyal kuyruğu |
| `mina-dashboard-ws` | WebSocket :8765 |
| `mina-dashboard-vite` | Dashboard :3000 |

---

## Sık karşılaşılan sorunlar

| Sorun | Çözüm |
|-------|--------|
| `ModuleNotFoundError: signal_bot` | `PYTHONPATH=/root/MINA_v2` veya parser bootstrap |
| Makro panel boş | `mina-dashboard-ws` → `dashboard/dashboard_ws.py` çalıştığından emin ol |
| `-1003` rate limit | Motor interval 30s+, WS 15s, health scriptleri lokal çalıştır |
| Görsel parser atlanıyor | `.env` içinde `ANTHROPIC_API_KEY` kontrol et |

---

**Toplam adım sayısı: 9** — tahmini kurtarma süresi **30–45 dk**.
