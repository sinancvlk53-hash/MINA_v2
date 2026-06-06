#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINA v2 — sağlık raporu 19-40 (API minimal)."""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

def section(n, title):
    print("\n" + "=" * 80)
    print(f"{n}) {title}")
    print("=" * 80)

# 19 archive + dead code scan
section(19, "Pasif / kullanılmayan dosyalar")
print("--- _archive/ tree ---")
r = subprocess.run(["find", f"{ROOT}/_archive", "-type", "f"], capture_output=True, text=True)
print(r.stdout.strip() or "(boş)")
if os.path.isfile(f"{ROOT}/_archive/README.md"):
    with open(f"{ROOT}/_archive/README.md", encoding="utf-8") as f:
        print(f.read())

for dead in [
    "signal_bot/ht_listener.py",
    "signal_bot/pdf_listener.py",
    "signal_bot/merter_tracker.py",
    "signal_bot/tracker.py",
    "backend/position_manager.py",
]:
    p = f"{ROOT}/{dead}"
    print(f"\n{dead}: exists={os.path.isfile(p)}")
    r2 = subprocess.run(
        ["grep", "-rl", os.path.basename(dead).replace(".py", ""), ROOT, "--include=*.service"],
        capture_output=True, text=True, errors="replace",
    )
    svc = [x for x in r2.stdout.splitlines() if "venv" not in x and dead not in x][:5]
    print(f"  systemd refs: {svc or '(yok)'}")

print("\n--- Aktif systemd servisleri ---")
r = subprocess.run(
    ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
    capture_output=True, text=True,
)
for ln in r.stdout.splitlines():
    if "mina" in ln.lower():
        print(ln)

print("\n--- pgrep listener prosesleri ---")
r = subprocess.run(["pgrep", "-af", "signal_bot/"], capture_output=True, text=True, errors="replace")
print(r.stdout.strip())

# 20 checklist
section(20, "Canlıya geçiş — MINA_ANAYASASI checklist")
checklist = f"{ROOT}/MINA_ANAYASASI.md"
if os.path.isfile(checklist):
    in_section = False
    for ln in open(checklist, encoding="utf-8"):
        if "GERÇEK HESAP ÖNCESİ" in ln:
            in_section = True
        if in_section:
            print(ln.rstrip())
else:
    print("(MINA_ANAYASASI.md yok)")

print("\n--- grep trailing algo / D3 test log ---")
for pat in ["algo/trailing", "trailing.*algo", "D3 gerçekleştirildi", "D3 ekleme", "D3 SFP"]:
    r = subprocess.run(
        ["grep", "-i", pat, f"{ROOT}/mina_bot.log"],
        capture_output=True, text=True, errors="replace",
    )
    lines = r.stdout.strip().splitlines()
    print(f"grep '{pat}' mina_bot.log: {len(lines)} satir, son 3:")
    for ln in lines[-3:]:
        print(f"  {ln}")

# 21 dashboard - read settings file only
section(21, "Dashboard pozisyon kaynağı (kod referans)")
print("dashboard_ws.py get_data(): client.futures_position_information() — DERR DEĞİL Binance")
print("slotType merter: sym in merter_by_sym AND lev==1 AND side==LONG")
print("SOL/LINK 4x → motor | NXPC 1x merter_other → merter")

# 22 macro full file
section(22, "macro_levels.json tam içerik")
mp = f"{ROOT}/signal_bot/macro_levels.json"
if os.path.isfile(mp):
    st = os.stat(mp)
    print(f"mtime UTC: {datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()}")
    print(open(mp, encoding="utf-8").read())
else:
    print("(yok)")

print("\n--- panel_levels_for_dashboard() ---")
try:
    sys.path.insert(0, os.path.join(ROOT, "signal_bot"))
    from macro_levels_store import panel_levels_for_dashboard
    for row in panel_levels_for_dashboard():
        snip = (row.get("snippet") or "")[:60]
        print(f"  {row.get('coin')}: snippet_len={len(row.get('snippet') or '')} dir={row.get('direction')} src={row.get('source')}")
except Exception as e:
    print(f"HATA: {e}")

# 23 mobile - code note
section(23, "Dashboard mobil (kod analizi)")
print("App.jsx: mobileTab positions|order|defense|settings")
print("PositionTable mobile: motor + merter sections stacked; LINK in motor (4x)")
print("MacroLevelsPanel mobile: only on positions tab (col-center)")
print("WS_URL hardcoded: ws://178.105.150.40:8765")

# 24 log rotation
section(24, "Log rotasyonu")
for p in [
    f"{ROOT}/mina_bot.log",
    f"{ROOT}/signal_bot/signals_log.txt",
    f"{ROOT}/signal_bot/merter_dca.log",
]:
    if os.path.isfile(p):
        st = os.stat(p)
        print(f"{p}: {st.st_size} bytes mtime={datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()}")
r = subprocess.run(["ls", "-la", "/etc/logrotate.d/"], capture_output=True, text=True)
print(r.stdout)
r = subprocess.run(["grep", "-rl", "mina", "/etc/logrotate.d/"], capture_output=True, text=True)
print("logrotate mina:", r.stdout.strip() or "(yok)")

# 25 server health
section(25, "Sunucu genel sağlık")
for cmd in ["uptime", "df -h /", "free -h", "top -bn1 | head -5"]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace")
    print(f"$ {cmd}\n{r.stdout.strip()}\n")

# 26 DERR quality
section(26, "DERR veri kalitesi")
db = f"{ROOT}/mina_trading_journal.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("--- Kapalı: null/0 alanlar ---")
for q in [
    "SELECT COUNT(*) c FROM trades WHERE status='closed' AND (close_price IS NULL OR close_price=0)",
    "SELECT COUNT(*) c FROM trades WHERE status='closed' AND (pnl_usdt IS NULL)",
    "SELECT COUNT(*) c FROM trades WHERE status='closed' AND (roe_percent IS NULL)",
    "SELECT COUNT(*) c FROM trades WHERE status='closed' AND weighted_avg_price IS NOT NULL",
    "SELECT id,symbol,side,close_reason,close_price,pnl_usdt,roe_percent,weighted_avg_price FROM trades WHERE status='closed' AND (close_price IS NULL OR close_price=0 OR pnl_usdt IS NULL) LIMIT 10",
]:
    if "LIMIT" in q:
        for row in conn.execute(q):
            print(dict(row))
    else:
        print(f"{q.split('FROM')[0].strip()}: {conn.execute(q).fetchone()[0]}")

print("\n--- Son 5 kapalı işlem ---")
for row in conn.execute(
    "SELECT id,symbol,side,leverage,open_price,close_price,pnl_usdt,roe_percent,close_reason,weighted_avg_price,defense_triggered FROM trades WHERE status='closed' ORDER BY id DESC LIMIT 5"
):
    print(dict(row))

print("\n--- Açık weighted_avg / defense ---")
for row in conn.execute("SELECT id,symbol,open_qty,defense_triggered,weighted_avg_price FROM trades WHERE status='open'"):
    print(dict(row))

# 27 duplicate
section(27, "Duplicate sinyal koruması")
print("signal_slot_bridge._open_position_keys: açık pozisyon key seti")
print("score_entry: _is_trade_candidate + open_keys kontrolü")
print("merter_dca: _yuva_busy per slot; ATOM merter_ei_2 — motor aynı coin ayrı kontrol YOK")

# 28 telegram
section(28, "Telegram bildirimleri son 12 saat")
for logf in [f"{ROOT}/mina_bot.log", f"{ROOT}/signal_bot/merter_dca.log"]:
    print(f"\n--- grep Telegram/send_notification {logf} ---")
    r = subprocess.run(
        ["grep", "-iE", "telegram|send_notification|Telegram|📢|🛡|KAPAT|AÇILDI", logf],
        capture_output=True, text=True, errors="replace",
    )
    lines = r.stdout.strip().splitlines()
    print(f"toplam {len(lines)} satir, son 15:")
    for ln in lines[-15:]:
        print(ln)

if os.path.isfile(f"{ROOT}/dashboard_settings.json"):
    print("\ndashboard_settings.json:")
    print(open(f"{ROOT}/dashboard_settings.json").read())

print("\nmotor_paused.flag exists:", os.path.isfile(f"{ROOT}/motor_paused.flag"))
try:
    from mina_dashboard_settings import is_motor_paused, load_settings
    print(f"is_motor_paused()={is_motor_paused()}")
    print(f"load_settings()={load_settings()}")
except Exception as e:
    print(f"settings import: {e}")

# 29-30 covered above

section(31, "Binance API rate limit son 24 saat")
r = subprocess.run(
    ["grep", "-i", "1003\\|too many requests\\|rate limit", f"{ROOT}/mina_bot.log"],
    capture_output=True, text=True, errors="replace",
)
lines = r.stdout.strip().splitlines()
print(f"mina_bot.log rate limit satirlari: {len(lines)}")
for ln in lines[-10:]:
    print(ln)
r2 = subprocess.run(
    ["journalctl", "--since", "24 hours ago", "--no-pager", "-u", "mina-engine.service"],
    capture_output=True, text=True, errors="replace",
)
rl = [ln for ln in r2.stdout.splitlines() if "1003" in ln or "too many" in ln.lower()]
print(f"journalctl engine rate limit: {len(rl)}")
for ln in rl[-5:]:
    print(ln)

section(32, "Testnet vs canlı")
env_path = f"{ROOT}/.env"
if os.path.isfile(env_path):
    for ln in open(env_path, encoding="utf-8"):
        if any(x in ln.upper() for x in ("BINANCE", "TESTNET", "API", "URL")):
            k = ln.split("=")[0] if "=" in ln else ln[:30]
            print(f"  {k}=***")
print("\ngrep testnet URL kod:")
r = subprocess.run(
    ["grep", "-rn", "testnet.binance", ROOT, "--include=*.py"],
    capture_output=True, text=True, errors="replace",
)
print(r.stdout.strip()[:3000] or "(yok)")

section(33, "Backup ve recovery")
for p in [f"{ROOT}/BACKUP", f"{ROOT}/backups", "/root/backups"]:
    if os.path.isdir(p):
        r = subprocess.run(["ls", "-lt", p], capture_output=True, text=True)
        print(f"--- {p} ---\n{r.stdout[:1500]}")
r = subprocess.run(["find", ROOT, "-maxdepth", "2", "-name", "*RECOVER*", "-o", "-name", "*backup*"], capture_output=True, text=True)
print("recovery docs:", r.stdout.strip() or "(yok)")

section(34, "Performans — motor döngü süresi")
r = subprocess.run(
    ["grep", "-E", "⏰|interval|Döngü", f"{ROOT}/mina_bot.log"],
    capture_output=True, text=True, errors="replace",
)
lines = r.stdout.strip().splitlines()
print(f"son 10 zaman damgasi satiri:")
for ln in lines[-10:]:
    print(ln)

section(35, "DERR signal_source NULL")
for q in [
    "SELECT COUNT(*) FROM trades WHERE signal_source IS NULL",
    "SELECT COUNT(*) FROM trades WHERE signal_source IS NULL AND status='open'",
    "SELECT id,symbol,side,status,signal_source,open_time FROM trades WHERE signal_source IS NULL ORDER BY id DESC LIMIT 15",
]:
    if "LIMIT" in q:
        for row in conn.execute(q):
            print(dict(row))
    else:
        print(f"{q}: {conn.execute(q).fetchone()[0]}")

section(36, "Haluk PDF parser — approved sinyaller")
queue = json.load(open(f"{ROOT}/signal_bot/raw_signal_queue.json", encoding="utf-8"))
entries = queue.get("entries") or []
pdf_approved = [e for e in entries if "pdf" in str(e.get("source", "")).lower() and e.get("status") == "approved"]
haluk_approved = [e for e in entries if "haluk" in str(e.get("source", "")).lower() and e.get("status") == "approved"]
print(f"queue pdf+approved: {len(pdf_approved)}")
print(f"queue haluk+approved: {len(haluk_approved)}")
for e in haluk_approved[-10:]:
    print(json.dumps({k: e.get(k) for k in ("symbol", "direction", "source", "status", "timestamp", "queue_state")}, ensure_ascii=False))

print("\n--- Son 5 PDF parse (signals_log) ---")
r = subprocess.run(
    ["grep", "HALUK PDF", f"{ROOT}/signal_bot/signals_log.txt"],
    capture_output=True, text=True, errors="replace",
)
for ln in r.stdout.strip().splitlines()[-10:]:
    print(ln)

section(37, "merter_ei_1 süzgeçli slot")
mdca = json.load(open(f"{ROOT}/signal_bot/merter_dca_state.json", encoding="utf-8"))
print("merter_ei_1 state:", json.dumps((mdca.get("positions") or {}).get("merter_ei_1"), ensure_ascii=False))
r = subprocess.run(["grep", "merter_ei_1", f"{ROOT}/signal_bot/merter_dca.log"], capture_output=True, text=True, errors="replace")
print(f"merter_dca.log merter_ei_1 satirlari: {len(r.stdout.splitlines())}")
for ln in r.stdout.strip().splitlines()[-15:]:
    print(ln)
r2 = subprocess.run(["grep", "-i", "ei_1\\|süzgeçli\\|filtered", f"{ROOT}/signal_bot/merter_dca_filter.log"], capture_output=True, text=True, errors="replace")
print(f"filter.log satirlari: {len(r2.stdout.splitlines())}, son 10:")
for ln in r2.stdout.strip().splitlines()[-10:]:
    print(ln)

conn.execute("""
SELECT COUNT(*) FROM trades WHERE signal_source='merter_ei_1'
""")
print("DERR merter_ei_1 trades:", conn.execute("SELECT COUNT(*) FROM trades WHERE signal_source='merter_ei_1'").fetchone()[0])

section(38, "Kaldıraç TP/stop — DERR leverage dağılımı")
for row in conn.execute("SELECT leverage, COUNT(*) c FROM trades GROUP BY leverage ORDER BY leverage"):
    print(dict(row))

section(39, "Slot köprüsü Haluk açılışları")
r = subprocess.run(
    ["grep", "-i", "SLOT_BRIDGE.*Açıldı\\|SLOT_BRIDGE.*Acildi", f"{ROOT}/mina_bot.log"],
    capture_output=True, text=True, errors="replace",
)
lines = r.stdout.strip().splitlines()
print(f"SLOT_BRIDGE Açıldı satirlari: {len(lines)}")
for ln in lines:
    print(ln)
r2 = subprocess.run(["grep", "SLOT_BRIDGE", "/var/log/syslog"], capture_output=True, text=True, errors="replace")
print(f"syslog SLOT_BRIDGE: {len(r2.stdout.splitlines())}")

ht_opens = conn.execute(
    "SELECT id,symbol,signal_source,open_time FROM trades WHERE signal_source IN ('HT','haluk_telegram','haluk_pdf','HALUK') ORDER BY id"
).fetchall()
print(f"DERR HT/haluk source trades: {len(ht_opens)}")
for row in ht_opens:
    print(dict(row))

section(40, "Dashboard build tarihi")
for p in [
    f"{ROOT}/dashboard/dist/index.html",
    f"{ROOT}/dashboard/dist/assets/index-C7r0r5AX.js",
]:
    if os.path.isfile(p):
        st = os.stat(p)
        print(f"{p}: mtime={datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()} size={st.st_size}")
print("\ndist/index.html:")
print(open(f"{ROOT}/dashboard/dist/index.html", encoding="utf-8").read()[:500])

conn.close()
print("\n" + "=" * 80)
print(f"Rapor bitisi UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
