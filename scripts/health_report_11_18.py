#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINA v2 — sağlık raporu maddeler 11-18 (ham çıktı)."""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import mina_tracking as mt
from config import BinanceConfig

def section(n, title):
    print("\n" + "=" * 80)
    print(f"{n}) {title}")
    print("=" * 80)

# ── 11 D1 bug — kod satırları ──
section(11, "D1 bug kontrolü — kod")
for rel in ["mina_position_manager.py", "main.py"]:
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        path = os.path.join(ROOT, "backend", rel)
    if not os.path.isfile(path):
        continue
    print(f"\n>>> grep execute_defense_action / _execute_d1 / idempotency in {rel}")
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    keys = ("execute_defense_action", "_execute_d1", "defense_triggered", "idempot", "journal", "DEFENSE_FILE", "defense_levels")
    for i, ln in enumerate(lines, 1):
        if any(k.lower() in ln.lower() for k in keys):
            if "execute_defense" in ln or "_execute_d1" in ln or "defense_triggered" in ln or "idempot" in ln.lower():
                print(f"  {i:5d}| {ln.rstrip()}")

# show _execute_d1 full function
mpm = os.path.join(ROOT, "mina_position_manager.py")
if os.path.isfile(mpm):
    with open(mpm, encoding="utf-8") as f:
        src = f.read()
    idx = src.find("def _execute_d1")
    if idx >= 0:
        end = src.find("\n    def ", idx + 1)
        if end < 0:
            end = idx + 4000
        print("\n>>> _execute_d1() tam fonksiyon:")
        chunk = src[idx:end]
        for i, ln in enumerate(chunk.splitlines(), 1):
            print(f"  {ln}")

    idx2 = src.find("def execute_defense_action")
    if idx2 >= 0:
        end2 = src.find("\n    def ", idx2 + 1)
        if end2 < 0:
            end2 = idx2 + 5000
        print("\n>>> execute_defense_action() tam fonksiyon:")
        for ln in src[idx2:end2].splitlines():
            print(f"  {ln}")

# ── 12 Merter DCA limit iptal ──
section(12, "Merter DCA limit iptal kontrolü")
for rel in ["main.py", "mina_position_manager.py"]:
    p = os.path.join(ROOT, rel)
    if os.path.isfile(p):
        print(f"\n>>> grep _cancel_merter_dca_limits in {rel}")
        with open(p, encoding="utf-8") as f:
            for i, ln in enumerate(f, 1):
                if "_cancel_merter_dca" in ln or "cancel_merter" in ln.lower():
                    print(f"  {i:5d}| {ln.rstrip()}")

print("\n--- mina_bot.log _cancel_merter / DCA limit iptal (son 12 saat filtre) ---")
log_path = os.path.join(ROOT, "mina_bot.log")
cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
if os.path.isfile(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            ll = line.lower()
            if any(x in ll for x in ("cancel_merter", "dca limit", "merter_dca", "limit iptal", "zaman stop", "stop-loss", "stop_loss")):
                print(line.rstrip())

print("\n--- merter_dca.log limit iptal / ATOM / NXPC ---")
mdca_log = os.path.join(ROOT, "signal_bot", "merter_dca.log")
if os.path.isfile(mdca_log):
    with open(mdca_log, encoding="utf-8", errors="replace") as f:
        for line in f:
            if any(x in line for x in ("iptal", "cancel", "ATOM", "NXPC", "LIMIT")):
                print(line.rstrip())

client = BinanceConfig().get_client()
print("\n--- Binance acik LIMIT emirler ATOM ---")
try:
    atom_orders = client.futures_get_open_orders(symbol="ATOMUSDT")
    if atom_orders:
        for o in atom_orders:
            print(json.dumps(o, ensure_ascii=False))
    else:
        print("(ATOMUSDT acik emir yok)")
except Exception as e:
    print(f"HATA: {e}")

print("\n--- Binance acik LIMIT emirler NXPC ---")
try:
    nxpc_orders = client.futures_get_open_orders(symbol="NXPCUSDT")
    print(f"count={len(nxpc_orders)}")
    for o in nxpc_orders:
        print(f"  orderId={o.get('orderId')} price={o.get('price')} qty={o.get('origQty')} status={o.get('status')}")
except Exception as e:
    print(f"HATA: {e}")

# ── 13 Slot köprüsü ──
section(13, "Slot köprüsü — son 12 saat")
bridge_files = [
    os.path.join(ROOT, "signal_bot", "signal_slot_bridge.py"),
    os.path.join(ROOT, "mina_bot.log"),
    os.path.join(ROOT, "signal_bot", "signals_log.txt"),
]
print(">>> grep try_fill_freed_slot in signal_slot_bridge.py")
bridge_py = os.path.join(ROOT, "signal_bot", "signal_slot_bridge.py")
if os.path.isfile(bridge_py):
    with open(bridge_py, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if "try_fill_freed_slot" in ln or "freed_slot" in ln or "slot_bridge" in ln.lower():
                print(f"  {i:5d}| {ln.rstrip()}")

for logf in [log_path, os.path.join(ROOT, "signal_bot", "merter_dca.log")]:
    if not os.path.isfile(logf):
        continue
    print(f"\n--- {logf} slot/köprü/try_fill ---")
    with open(logf, encoding="utf-8", errors="replace") as f:
        for line in f:
            ll = line.lower()
            if any(x in ll for x in ("try_fill_freed_slot", "freed_slot", "slot_bridge", "slot köpr", "slot bridge", "fill_freed", "boş slot")):
                print(line.rstrip())

# journal queue-watcher
r = subprocess.run(
    ["journalctl", "--since", "12 hours ago", "--no-pager", "-u", "mina-queue-watcher.service"],
    capture_output=True, text=True, errors="replace",
)
print("\n--- journalctl mina-queue-watcher son 12 saat (slot/köprü satırları) ---")
for ln in r.stdout.splitlines():
    ll = ln.lower()
    if any(x in ll for x in ("slot", "bridge", "fill", "freed", "köpr", "queue")):
        print(ln)

# grep main for try_fill
main_py = os.path.join(ROOT, "main.py")
if os.path.isfile(main_py):
    print("\n>>> grep try_fill_freed_slot in main.py")
    with open(main_py, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if "try_fill_freed_slot" in ln or "fill_freed" in ln:
                print(f"  {i:5d}| {ln.rstrip()}")

# ── 14 Sinyal TTL ──
section(14, "Sinyal TTL kontrolü")
sys.path.insert(0, os.path.join(ROOT, "signal_bot"))
try:
    from signal_slot_bridge import QUEUE_TTL_SEC, expire_stale_queue_entries
    print(f"QUEUE_TTL_SEC = {QUEUE_TTL_SEC}")
except Exception as e:
    print(f"import hata: {e}")
    QUEUE_TTL_SEC = "?"

queue_path = os.path.join(ROOT, "signal_bot", "raw_signal_queue.json")
queue = json.load(open(queue_path, encoding="utf-8"))
entries = queue.get("entries") or []
print(f"\ntoplam entry: {len(entries)}")

ttl_marked = [e for e in entries if e.get("queue_state") == "queue_ttl_30m" or e.get("cancel_reason") == "queue_ttl_30m" or "ttl" in str(e.get("queue_state", "")).lower()]
print(f"queue_ttl_30m / ttl işaretli: {len(ttl_marked)}")
for e in ttl_marked[:20]:
    print(json.dumps({k: e.get(k) for k in ("symbol", "direction", "timestamp", "queue_state", "status", "cancel_reason")}, ensure_ascii=False))

expired_cancelled = [e for e in entries if e.get("queue_state") in ("expired", "cancelled") and ("ttl" in str(e.get("cancel_reason", "")).lower() or "ttl" in str(e.get("queue_state", "")).lower())]
print(f"\nexpired/cancelled TTL nedeniyle: {len(expired_cancelled)}")
for e in expired_cancelled[-15:]:
    print(json.dumps({k: e.get(k) for k in ("symbol", "direction", "timestamp", "queue_state", "status", "cancel_reason")}, ensure_ascii=False))

# bridge source for TTL logic
if os.path.isfile(bridge_py):
    print("\n>>> TTL ile ilgili satırlar signal_slot_bridge.py")
    with open(bridge_py, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if "ttl" in ln.lower() or "expire" in ln.lower() or "1800" in ln or "30" in ln and "min" in ln.lower():
                print(f"  {i:5d}| {ln.rstrip()}")

# logs TTL
sig_log = os.path.join(ROOT, "signal_bot", "signals_log.txt")
print("\n--- signals_log TTL/expire son 12 saat ---")
if os.path.isfile(sig_log):
    with open(sig_log, encoding="utf-8", errors="replace") as f:
        for line in f:
            if any(x in line.lower() for x in ("ttl", "expire", "süresi doldu", "stale")):
                print(line.rstrip())

# ── 15 Kasa formülü ──
section(15, "Kasa formülü doğrulama")
bal = client.futures_account_balance()
usdt = next((b for b in bal if b.get("asset") == "USDT"), {})
print("Binance futures USDT RAW:")
for k in sorted(usdt.keys()):
    print(f"  {k}: {usdt[k]}")

wallet = float(usdt.get("balance") or 0)
avail = float(usdt.get("availableBalance") or usdt.get("available") or 0)
print(f"\nbalance={wallet} available={avail}")

# import slot calc from codebase
try:
    import mina_slot_policy as msp
    print(f"\nmina_slot_policy modül: {msp.__file__}")
    for name in dir(msp):
        if "slot" in name.lower() or "margin" in name.lower() or "kasa" in name.lower():
            obj = getattr(msp, name)
            if callable(obj) and not name.startswith("_"):
                try:
                    r = obj()
                    print(f"  {name}() = {r}")
                except TypeError:
                    try:
                        r = obj(wallet)
                        print(f"  {name}({wallet}) = {r}")
                    except Exception as ex:
                        print(f"  {name}: TypeError {ex}")
except Exception as e:
    print(f"mina_slot_policy import: {e}")

# main.py slot calc — dosyadan oku (import main motor logger'ı tetikler)
for mod_name in ("main", "mina_position_manager"):
    p = os.path.join(ROOT, f"{mod_name}.py")
    if not os.path.isfile(p):
        continue
    print(f"\n>>> slot/margin fonksiyonları {mod_name}.py")
    with open(p, encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f, 1):
            if "def " in ln and any(
                x in ln.lower() for x in ("slot", "margin", "kasa")
            ):
                print(f"  {i:5d}| {ln.rstrip()}")

# manual calc
slot_calc = wallet / 10
margin_calc = slot_calc / 5
print(f"\nMANUEL FORMÜL (balance/10, slot/5):")
print(f"  kasa={wallet}")
print(f"  slot=balance/10={slot_calc}")
print(f"  giris_marjini=slot/5={margin_calc}")

# check initial_margins recent
im = mt.load_json(mt.INITIAL_MARGIN_FILE)
print(f"\ninitial_margins.json (tam):")
print(json.dumps(im, indent=2))

# engine log recent slot mention
print("\n--- mina_bot.log slot/margin/kasa son satirlar ---")
if os.path.isfile(log_path):
    hits = []
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if any(x in line.lower() for x in ("slot", "kasa", "margin", "balance")):
                hits.append(line.rstrip())
    for ln in hits[-15:]:
        print(ln)

# ── 16 Haluk PDF ──
section(16, "Haluk PDF son durum")
macro_path = os.path.join(ROOT, "signal_bot", "macro_levels.json")
if os.path.isfile(macro_path):
    st = os.stat(macro_path)
    print(f"macro_levels.json mtime UTC: {datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()}")
    print(f"macro_levels.json size: {st.st_size} bytes")
    data = json.load(open(macro_path, encoding="utf-8"))
    print(f"keys count: {len(data) if isinstance(data, dict) else 'list'}")
    print("macro_levels.json (ilk 2000 char):")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
else:
    print("macro_levels.json YOK")

# PDF dir
for pdf_dir in [
    os.path.join(ROOT, "signal_bot", "pdfs"),
    os.path.join(ROOT, "signal_bot", "haluk_pdfs"),
    os.path.join(ROOT, "data", "pdfs"),
]:
    if os.path.isdir(pdf_dir):
        print(f"\nPDF dizin: {pdf_dir}")
        pdfs = sorted(
            [(f, os.path.getmtime(os.path.join(pdf_dir, f))) for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")],
            key=lambda x: x[1], reverse=True,
        )
        for f, mt in pdfs[:10]:
            print(f"  {f}  mtime={datetime.fromtimestamp(mt, tz=timezone.utc).isoformat()}")

print("\n--- signals_log HALUK PDF satirlari (son 30) ---")
if os.path.isfile(sig_log):
    haluk_pdf = []
    with open(sig_log, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "[HALUK]" in line and ("pdf" in line.lower() or "PDF" in line or "onay" in line.lower() or "approved" in line.lower()):
                haluk_pdf.append(line.rstrip())
    for ln in haluk_pdf[-30:]:
        print(ln)
    if not haluk_pdf:
        print("(PDF/onay satiri yok — son HALUK satirlari:)")
        with open(sig_log, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for ln in lines[-10:]:
            if "[HALUK]" in ln:
                print(ln.rstrip())

# haluk_pdf_parser log
print("\n--- grep PDF haluk mina_bot.log / signals_log ---")
for pat in ["PDF", "haluk_pdf", "macro_levels"]:
    r = subprocess.run(["grep", "-i", pat, sig_log], capture_output=True, text=True, errors="replace")
    lines = r.stdout.strip().splitlines()
    print(f"grep -i {pat} signals_log.txt: {len(lines)} satir, son 5:")
    for ln in lines[-5:]:
        print(ln)

# ── 17 GitHub sync ──
section(17, "GitHub son commit — sunucu senkron")
for cmd in [
    "cd /root/MINA_v2 && git rev-parse HEAD",
    "cd /root/MINA_v2 && git log -1 --oneline",
    "cd /root/MINA_v2 && git status --short",
    "cd /root/MINA_v2 && git remote -v",
    "cd /root/MINA_v2 && git branch -vv",
    "cd /root/MINA_v2 && (git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null || echo 'origin ref yok')",
]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace")
    print(f"$ {cmd}")
    print(r.stdout.strip() or "(boş)")
    if r.stderr.strip():
        print(f"stderr: {r.stderr.strip()}")

# ── 18 Disk bellek ──
section(18, "Disk ve bellek")
for cmd in [
    "df -h /",
    "free -h",
    "du -sh /root/MINA_v2/*.log /root/MINA_v2/signal_bot/*.log 2>/dev/null",
    "ls -lh /root/MINA_v2/mina_bot.log",
    "ls -lh /root/MINA_v2/signal_bot/merter_dca.log /root/MINA_v2/signal_bot/signals_log.txt 2>/dev/null",
    "du -sh /root/MINA_v2",
    "grep -r logrotate /etc/logrotate.d/ 2>/dev/null | grep -i mina || echo 'logrotate mina: yok'",
    "cat /etc/logrotate.d/mina 2>/dev/null || cat /etc/logrotate.d/mina-engine 2>/dev/null || echo 'logrotate config dosyasi bulunamadi'",
]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace")
    print(f"$ {cmd}")
    print(r.stdout.strip() or r.stderr.strip() or "(boş)")

print("\n" + "=" * 80)
print(f"Rapor bitisi UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
