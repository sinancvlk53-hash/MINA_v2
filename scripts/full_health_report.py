#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINA v2 — tam sistem sağlık raporu (ham çıktı)."""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)
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

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"__error__": str(e)}

client = BinanceConfig().get_client()
db = os.path.join(ROOT, "mina_trading_journal.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# ── 1 SOLUSDT D1 ──
section(1, "SOLUSDT D1 kontrolü")
defense = mt.load_json(mt.DEFENSE_FILE)
print("defense_levels.json SOLUSDT_LONG =", defense.get("SOLUSDT_LONG", "KEY_YOK"))
print("\ndefense_levels.json (tam):")
print(json.dumps(defense, indent=2, ensure_ascii=False))

for p in client.futures_position_information():
    if p["symbol"] != "SOLUSDT":
        continue
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    print("\nBinance SOLUSDT RAW:")
    for k in sorted(p.keys()):
        print(f"  {k}: {p[k]}")

row = conn.execute(
    "SELECT id, symbol, side, open_qty, defense_triggered, defense_prices, weighted_avg_price, status FROM trades WHERE symbol='SOLUSDT' AND status='open'"
).fetchone()
print("\nDERR SOLUSDT acik:")
print(dict(row) if row else "(yok)")

log_path = os.path.join(ROOT, "mina_bot.log")
d1_lines = []
if os.path.isfile(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "SOLUSDT" in line and ("defense" in line.lower() or "D1" in line or "d1" in line.lower()):
                d1_lines.append(line.rstrip())
print("\nmina_bot.log SOLUSDT defense/D1 satirlari:")
for ln in d1_lines[-20:]:
    print(ln)
if not d1_lines:
    print("(yok)")

grep_d1 = subprocess.run(
    ["grep", "-i", "D1 gerçekleştirildi", log_path],
    capture_output=True, text=True, errors="replace"
)
print("\ngrep 'D1 gerçekleştirildi' mina_bot.log:")
print(grep_d1.stdout.strip() if grep_d1.stdout.strip() else "(eşleşme yok)")

# initial entry for D1 line
iep = mt.load_json(mt.INITIAL_PRICE_FILE).get("SOLUSDT_LONG")
if iep:
    try:
        mark = float(client.futures_mark_price(symbol="SOLUSDT")["markPrice"])
        d1_line = float(iep) * 0.95
        print(f"\ninitial_entry={iep} d1_line={d1_line:.6f} mark={mark:.6f} d1_hit={mark <= d1_line}")
    except Exception as e:
        print(f"mark okuma: {e}")

# ── 2 LINKUSDT TP1 ──
section(2, "LINKUSDT TP1 kontrolü")
tp_levels = mt.load_json(mt.TP_FILE)
print("tp_levels.json LINKUSDT_LONG =", tp_levels.get("LINKUSDT_LONG", "KEY_YOK"))

for p in client.futures_position_information():
    if p["symbol"] != "LINKUSDT":
        continue
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    print("\nBinance LINKUSDT RAW:")
    for k in sorted(p.keys()):
        print(f"  {k}: {p[k]}")

link_derr = conn.execute(
    "SELECT id, open_qty, open_price, close_time, status, signal_source FROM trades WHERE symbol='LINKUSDT' ORDER BY id DESC LIMIT 3"
).fetchall()
print("\nDERR LINKUSDT (son kayitlar):")
for r in link_derr:
    print(dict(r))

link_tp_log = []
if os.path.isfile(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "LINKUSDT" in line and "take_profit" in line:
                link_tp_log.append(line.rstrip())
print("\nmina_bot.log LINKUSDT take_profit:")
for ln in link_tp_log:
    print(ln)

state = load_json(os.path.join(ROOT, "mina_position_state.json"))
print("\nmina_position_state.json LINKUSDT:")
print(json.dumps(state.get("LINKUSDT"), indent=2, ensure_ascii=False))

# Compare qty: open_qty in DERR vs binance
link_row = conn.execute("SELECT open_qty FROM trades WHERE symbol='LINKUSDT' AND status='open'").fetchone()
if link_row:
    print(f"\nDERR open_qty={link_row['open_qty']} vs Binance positionAmt (yukarıda)")

# ── 3 NXPCUSDT ──
section(3, "NXPCUSDT durumu")
for p in client.futures_position_information():
    if p["symbol"] != "NXPCUSDT":
        continue
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    print("Binance NXPCUSDT RAW:")
    for k in sorted(p.keys()):
        print(f"  {k}: {p[k]}")
    tp2 = entry * 1.05 if entry else None
    print(f"\nentry={entry} mark={mark} TP2_esik(avg*1.05)={tp2}")

mdca = load_json(os.path.join(ROOT, "signal_bot", "merter_dca_state.json"))
print("\nmerter_dca_state.json (tam):")
print(json.dumps(mdca, indent=2, ensure_ascii=False))

nxpc_derr = conn.execute(
    "SELECT * FROM trades WHERE symbol='NXPCUSDT' AND status='open'"
).fetchone()
print("\nDERR NXPCUSDT acik:")
print(dict(nxpc_derr) if nxpc_derr else "(yok)")

print("\nBinance NXPCUSDT acik LIMIT emirler:")
try:
    orders = client.futures_get_open_orders(symbol="NXPCUSDT")
    if not orders:
        print("(limit emir yok)")
    for o in orders:
        print(json.dumps(o, ensure_ascii=False))
except Exception as e:
    print(f"HATA: {e}")

# merter log TP1
mdca_log = os.path.join(ROOT, "signal_bot", "merter_dca.log")
if os.path.isfile(mdca_log):
    print("\nmerter_dca.log NXPCUSDT satirlari:")
    with open(mdca_log, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "NXPC" in line:
                print(line.rstrip())

# ── 4 JSON tutarlılık ──
section(4, "Tüm JSON dosyaları")
files = {
    "initial_entry_prices.json": mt.load_json(mt.INITIAL_PRICE_FILE),
    "initial_margins.json": mt.load_json(mt.INITIAL_MARGIN_FILE),
    "defense_levels.json": mt.load_json(mt.DEFENSE_FILE),
    "tp_levels.json": mt.load_json(mt.TP_FILE),
    "max_prices.json": mt.load_json(mt.MAX_PRICE_FILE),
    "position_sources.json": mt.load_json("position_sources.json"),
    "mina_position_state.json": load_json(os.path.join(ROOT, "mina_position_state.json")),
    "merter_dca_state.json": load_json(os.path.join(ROOT, "signal_bot", "merter_dca_state.json")),
    "pending_orders.json": mt.load_json(mt.PENDING_ORDERS_FILE),
}
for fn, data in files.items():
    print(f"\n>>> {fn}")
    print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n--- DERR acik kayitlar ---")
derr_open = conn.execute(
    "SELECT id, symbol, side, leverage, open_price, open_qty, initial_margin, signal_source, defense_triggered FROM trades WHERE status='open' ORDER BY id"
).fetchall()
for r in derr_open:
    print(dict(r))

print("\n--- Binance acik keys ---")
binance_keys = set()
for p in client.futures_position_information():
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    side = "LONG" if amt > 0 else "SHORT"
    binance_keys.add(mt.pos_key(p["symbol"], side))
print("Binance:", sorted(binance_keys))

derr_keys = {mt.pos_key(r["symbol"], r["side"]) for r in derr_open}
print("DERR:", sorted(derr_keys))

tracking_keys = set(files["initial_entry_prices.json"].keys())
print("initial_entry_prices keys:", sorted(tracking_keys))

only_bin = binance_keys - derr_keys
only_derr = derr_keys - binance_keys
only_track = tracking_keys - binance_keys
print(f"\nSadece Binance: {sorted(only_bin)}")
print(f"Sadece DERR: {sorted(only_derr)}")
print(f"Tracking'te var Binance'te yok: {sorted(only_track)}")

# ── 5 Servisler ──
section(5, "Systemd servisleri")
services = [
    "mina-engine", "mina-listener", "mina-merter-dca",
    "mina-queue-watcher", "mina-dashboard-ws", "mina-dashboard-vite",
]
for s in services:
    r = subprocess.run(["systemctl", "is-active", s + ".service"], capture_output=True, text=True)
    print(f"{s}.service: {r.stdout.strip()}")

print("\n--- systemctl status (kısa) ---")
for s in services:
    r = subprocess.run(
        ["systemctl", "show", s + ".service", "--property=ActiveState,SubState,ActiveEnterTimestamp,NRestarts,Result"],
        capture_output=True, text=True,
    )
    print(f"[{s}]")
    print(r.stdout.strip())

print("\n--- Son 1 saat restart/crash (journalctl) ---")
r = subprocess.run(
    [
        "journalctl", "--since", "1 hour ago", "--no-pager",
        "-u", "mina-engine.service", "-u", "mina-listener.service",
        "-u", "mina-merter-dca.service", "-u", "mina-queue-watcher.service",
        "-u", "mina-dashboard-ws.service", "-u", "mina-dashboard-vite.service",
        "-p", "err",
    ],
    capture_output=True, text=True, errors="replace",
)
print(r.stdout.strip() if r.stdout.strip() else "(err seviyesinde kayit yok)")

print("\n--- journalctl Started/Stopped son 1 saat ---")
r2 = subprocess.run(
    [
        "journalctl", "--since", "1 hour ago", "--no-pager",
        "-u", "mina-engine.service", "-u", "mina-listener.service",
        "-u", "mina-merter-dca.service",
        "--grep", "Started|Stopped|Failed|restart",
    ],
    capture_output=True, text=True, errors="replace",
)
print(r2.stdout.strip() if r2.stdout.strip() else "(eşleşme yok)")

# ── 6 Listener ──
section(6, "Listener sağlığı")
sig_log = os.path.join(ROOT, "signal_bot", "signals_log.txt")
if os.path.isfile(sig_log):
    with open(sig_log, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print("signals_log.txt son 5 satir:")
    for ln in lines[-5:]:
        print(ln.rstrip())
    haluk = sum(1 for l in lines[-50:] if "[HALUK]" in l and "dinleniyor" in l)
    merter = sum(1 for l in lines[-50:] if "[MERTER]" in l and "dinleniyor" in l)
    print(f"\nSon 50 satirda 'dinleniyor' HALUK={haluk} MERTER={merter}")
else:
    print("(signals_log yok)")

lock = os.path.join(ROOT, "signal_bot", "listener.lock")
print(f"\nlistener.lock: ", end="")
if os.path.isfile(lock):
    with open(lock) as f:
        pid = f.read().strip()
    print(f"pid={pid}")
    r = subprocess.run(["ps", "-p", pid, "-o", "pid,cmd"], capture_output=True, text=True)
    print(r.stdout.strip() if r.returncode == 0 else f"PID {pid} calismiyor")
else:
    print("yok")

# ── 7 Hayalet ──
section(7, "Hayalet pozisyon kontrolü")
merter_keys_fn = lambda: set()
try:
    from ghost_positions import scan_and_report, merter_dca_tracked_keys
    merter_keys_fn = merter_dca_tracked_keys
    try:
        ghosts = scan_and_report(client, verbose=False, telegram=False)
    except TypeError:
        ghosts = scan_and_report(client)
    print(f"scan_and_report ghost sayisi: {len(ghosts)}")
    for g in ghosts:
        print(json.dumps(g, ensure_ascii=False, default=str))
except Exception as e:
    print(f"ghost scan hata: {e}")
    ghosts = []

print("\nMarjin>0 ama tracking disi:")
tracked = set(mt.load_json(mt.INITIAL_PRICE_FILE).keys()) | merter_keys_fn()
for p in client.futures_position_information():
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    side = "LONG" if amt > 0 else "SHORT"
    key = mt.pos_key(p["symbol"], side)
    m = float(p.get("isolatedMargin") or 0)
    if key not in tracked and m > 0:
        print(f"  UNTRACKED: {key} margin={m} lev={p.get('leverage')}")

# ── 8 Kuyruk ──
section(8, "raw_signal_queue.json")
queue = load_json(os.path.join(ROOT, "signal_bot", "raw_signal_queue.json"))
entries = queue.get("entries") or []
print(f"toplam entry: {len(entries)}")

approved_not_consumed = [
    e for e in entries
    if e.get("status") == "approved"
    and e.get("queue_state") not in ("consumed", "cancelled", "superseded", "expired", "pending_limit")
]
print(f"\napproved ama consumed degil: {len(approved_not_consumed)}")
for e in approved_not_consumed:
    print(json.dumps({
        "symbol": e.get("symbol"),
        "direction": e.get("direction"),
        "timestamp": e.get("timestamp"),
        "queue_state": e.get("queue_state"),
        "status": e.get("status"),
    }, ensure_ascii=False))

import time
from signal_bot.signal_slot_bridge import expire_stale_queue_entries, QUEUE_TTL_SEC
now = time.time()
stale = []
for e in entries:
    if e.get("queue_state") in ("consumed", "cancelled", "superseded"):
        continue
    ts = e.get("timestamp")
    if not ts:
        continue
    try:
        from signal_bot.signal_slot_bridge import _parse_entry_ts
        t = _parse_entry_ts(e)
        if t and (now - t) > QUEUE_TTL_SEC:
            stale.append(e)
    except Exception:
        pass
print(f"\nTTL dolmus aday (>{QUEUE_TTL_SEC}s): {len(stale)}")
for e in stale[:10]:
    print(json.dumps({"symbol": e.get("symbol"), "direction": e.get("direction"), "timestamp": e.get("timestamp"), "queue_state": e.get("queue_state")}, ensure_ascii=False))

# ── 9 DERR stats ──
section(9, "DERR istatistikleri")
total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
closed = conn.execute("SELECT COUNT(*) FROM trades WHERE status='closed'").fetchone()[0]
open_c = conn.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()[0]
wins = conn.execute("SELECT COUNT(*) FROM trades WHERE status='closed' AND pnl_usdt > 0").fetchone()[0]
losses = conn.execute("SELECT COUNT(*) FROM trades WHERE status='closed' AND pnl_usdt < 0").fetchone()[0]
realized = conn.execute("SELECT COALESCE(SUM(pnl_usdt),0) FROM trades WHERE status='closed'").fetchone()[0]
wr = (wins / (wins + losses) * 100) if (wins + losses) else 0
print(f"toplam_islem: {total}")
print(f"acik: {open_c}")
print(f"kapali: {closed}")
print(f"kazanan: {wins}")
print(f"kaybeden: {losses}")
print(f"win_rate: {wr:.2f}%")
print(f"toplam_realized_pnl_usdt: {float(realized):+.4f}")

# ── 10 Limit emirler ──
section(10, "Binance acik LIMIT emirler (tüm semboller)")
try:
    all_orders = client.futures_get_open_orders()
    limits = [o for o in all_orders if o.get("type") == "LIMIT"]
    print(f"toplam_acik_emir: {len(all_orders)} limit: {len(limits)}")
    for o in sorted(limits, key=lambda x: (x.get("symbol", ""), float(x.get("price") or 0))):
        print(
            f"  {o.get('symbol')} {o.get('side')} {o.get('positionSide')} "
            f"price={o.get('price')} qty={o.get('origQty')} "
            f"filled={o.get('executedQty')} orderId={o.get('orderId')} status={o.get('status')}"
        )
    if not limits:
        print("(acik LIMIT emir yok)")
except Exception as e:
    print(f"HATA: {e}")

conn.close()
print("\n" + "=" * 80)
print(f"Rapor bitisi UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
