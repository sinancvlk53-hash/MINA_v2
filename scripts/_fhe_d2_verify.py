#!/usr/bin/env python3
"""FHEUSDT D2 breakeven fix doğrulama (journal open_price + 90s bekleme)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

ROOT = "/root/MINA_v2"
KEY = "FHEUSDT_LONG"
SYM = "FHEUSDT"
TRADE_ID = 64
ENTRY_FILE = os.path.join(ROOT, "initial_entry_prices.json")
DEFENSE_FILE = os.path.join(ROOT, "defense_levels.json")
STATE_FILE = os.path.join(ROOT, "mina_position_state.json")
DB = os.path.join(ROOT, "mina_trading_journal.db")
LOG_FILE = os.path.join(ROOT, "mina_bot.log")
BACKUP_DIR = os.path.join(ROOT, "scripts", "_fhe_d2_verify_backup")

os.makedirs(BACKUP_DIR, exist_ok=True)
shutil.copy2(ENTRY_FILE, os.path.join(BACKUP_DIR, "initial_entry.json"))
shutil.copy2(DEFENSE_FILE, os.path.join(BACKUP_DIR, "defense.json"))
shutil.copy2(STATE_FILE, os.path.join(BACKUP_DIR, "state.json"))
shutil.copy2(DB, os.path.join(BACKUP_DIR, "journal.db.bak"))

sys.path.insert(0, ROOT)
from backend.config import BinanceConfig

client = BinanceConfig().get_client()
mark = float(client.futures_mark_price(symbol=SYM)["markPrice"])
fake_entry = round(mark / 0.87, 8)

# Journal open_price — boot sync bunu initial_entry yapar
conn = sqlite3.connect(DB, timeout=30)
orig_open = conn.execute("SELECT open_price FROM trades WHERE id=?", (TRADE_ID,)).fetchone()[0]
conn.execute("UPDATE trades SET open_price=?, defense_triggered=0 WHERE id=?", (fake_entry, TRADE_ID))
conn.commit()
conn.close()

defense = json.load(open(DEFENSE_FILE, encoding="utf-8"))
defense[KEY] = 0
with open(DEFENSE_FILE, "w", encoding="utf-8") as f:
    json.dump(defense, f, indent=2)
    f.write("\n")

state = json.load(open(STATE_FILE, encoding="utf-8"))
if SYM in state:
    s = state[SYM]
    s.update({
        "defense_stage": 0,
        "tp_disabled": False,
        "d2_order_active": False,
        "d2_order_id": None,
        "d3_order_id": None,
        "d2_triggered_at": None,
    })
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
    f.write("\n")

entry = json.load(open(ENTRY_FILE, encoding="utf-8"))
entry[KEY] = fake_entry
with open(ENTRY_FILE, "w", encoding="utf-8") as f:
    json.dump(entry, f, ensure_ascii=False, indent=2)
    f.write("\n")

with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
    log_start = sum(1 for _ in f)

print(f"=== FHE D2 TEST {datetime.now().isoformat(timespec='seconds')} ===")
print(f"mark={mark}")
print(f"initial_entry / journal open_price = {fake_entry} (mark/0.87)")
print(f"d1_line={fake_entry * 0.95:.8f} d2_line={fake_entry * 0.88:.8f}")
print("mina-engine restart → 90s bekle (D1 + D2 için 3 döngü)")
subprocess.run(["systemctl", "restart", "mina-engine"], check=True)
time.sleep(90)

jout = subprocess.check_output(
    ["journalctl", "-u", "mina-engine", "--since", "2 min ago", "--no-pager"],
    text=True,
    errors="replace",
)
fhe_journal = [ln for ln in jout.splitlines() if "FHE" in ln]

with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
    fhe_bot = [ln.rstrip() for ln in f.readlines()[log_start:] if "FHE" in ln]

defense_after = json.load(open(DEFENSE_FILE, encoding="utf-8"))
state_after = json.load(open(STATE_FILE, encoding="utf-8")).get(SYM, {})
entry_after = json.load(open(ENTRY_FILE, encoding="utf-8")).get(KEY)

print(f"\ninitial_entry_after={entry_after}")
print(f"defense_levels[{KEY}]={defense_after.get(KEY)}")
print(f"state defense_stage={state_after.get('defense_stage')} tp_disabled={state_after.get('tp_disabled')}")
print(f"d2_order_id={state_after.get('d2_order_id')}")

print("\n=== JOURNAL (FHE) ===")
for ln in fhe_journal:
    print(ln)
if not fhe_journal:
    print("(yok)")

print("\n=== mina_bot.log (FHE) ===")
for ln in fhe_bot:
    print(ln)
if not fhe_bot:
    print("(yok)")

orders = client.futures_get_open_orders(symbol=SYM)
print("\n=== AÇIK EMİRLER FHEUSDT ===")
for o in orders:
    print(json.dumps({
        "orderId": o.get("orderId"),
        "type": o.get("type"),
        "side": o.get("side"),
        "price": o.get("price"),
        "stopPrice": o.get("stopPrice"),
        "positionSide": o.get("positionSide"),
    }))
if not orders:
    print("(açık emir yok)")

all_logs = fhe_journal + fhe_bot
breakeven_ok = any("D2 yürütüldü" in ln or "D2 kaçış emri doğrulandı" in ln for ln in all_logs)
breakeven_fail = any("D2 emri başarısız" in ln for ln in all_logs)
d2_ok = defense_after.get(KEY, 0) >= 2 or int(state_after.get("defense_stage", 0)) >= 2
has_limit = any(o.get("type") == "LIMIT" and o.get("side") == "SELL" for o in orders)

print("\n=== SONUÇ ===")
print(f"D2 tetiklendi: {d2_ok}")
print(f"Breakeven emri (log): {breakeven_ok}")
print(f"Breakeven LIMIT açık: {has_limit}")
print(f"Hata (-4024): {breakeven_fail}")
if breakeven_ok and not breakeven_fail:
    print("VERDICT: ✅ Çalışıyor")
elif d2_ok and (breakeven_ok or has_limit) and not breakeven_fail:
    print("VERDICT: ⚠️ Kısmen")
else:
    print("VERDICT: ❌ Çalışmıyor")

# Geri yükle
shutil.copy2(os.path.join(BACKUP_DIR, "initial_entry.json"), ENTRY_FILE)
shutil.copy2(os.path.join(BACKUP_DIR, "defense.json"), DEFENSE_FILE)
shutil.copy2(os.path.join(BACKUP_DIR, "state.json"), STATE_FILE)
conn = sqlite3.connect(DB, timeout=30)
conn.execute("UPDATE trades SET open_price=?, defense_triggered=0 WHERE id=?", (orig_open, TRADE_ID))
conn.commit()
conn.close()
print(f"\nGeri yüklendi: initial_entry[{KEY}]={json.load(open(ENTRY_FILE))[KEY]} journal open={orig_open}")
subprocess.run(["systemctl", "restart", "mina-engine"], check=True)
