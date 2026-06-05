#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baş Mühendis soru seti — sunucu veri toplama."""
import json
import os
import sys
from datetime import datetime, timezone

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
ROOT = "/root/MINA_v2"

REMOTE = r'''#!/usr/bin/env python3
import json, os, sys, sqlite3
from datetime import datetime, timezone

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + "/backend")
os.chdir(ROOT)

def sep(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)

# --- SORU 1 PARTI userTrades ---
sep("SORU 1 — PARTIUSDT userTrades (bugün 2026-06-04 UTC)")
from dotenv import load_dotenv
load_dotenv(ROOT + "/.env")
from config import BinanceConfig
client = BinanceConfig().get_client()
import time
day_start = int(datetime(2026, 6, 4, tzinfo=timezone.utc).timestamp() * 1000)
day_end = int(datetime(2026, 6, 5, tzinfo=timezone.utc).timestamp() * 1000)
try:
    trades = client.futures_account_trades(symbol="PARTIUSDT", startTime=day_start, endTime=day_end, limit=1000)
    if not trades:
        print("(bugün trade yok — son 50 trade)")
        trades = client.futures_account_trades(symbol="PARTIUSDT", limit=50)
    print(f"{'time':<22} {'side':<5} {'posSide':<6} {'qty':>10} {'price':>12} {'realizedPnl':>12} {'commission':>10}")
    for t in trades:
        ts = datetime.fromtimestamp(t["time"]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts:<22} {t.get('side',''):<5} {t.get('positionSide',''):<6} {float(t['qty']):>10.4f} {float(t['price']):>12.6f} {float(t.get('realizedPnl',0)):>12.4f} {float(t.get('commission',0)):>10.4f}")
    print(f"\nToplam {len(trades)} kayıt")
except Exception as e:
    print("HATA:", e)

sep("PARTIUSDT açık pozisyonlar + marjin")
for p in client.futures_position_information():
    if p["symbol"] != "PARTIUSDT":
        continue
    amt = float(p.get("positionAmt", 0))
    if amt == 0:
        continue
    print(json.dumps({k: p.get(k) for k in ["symbol","positionAmt","entryPrice","markPrice","isolatedMargin","leverage","unRealizedProfit","positionSide"]}, indent=2))

# --- SORU 2 ZRO ---
sep("SORU 2 — ZROUSDT Merter DCA")
state = json.load(open(ROOT + "/signal_bot/merter_dca_state.json"))
zro = state.get("positions", {})
print("merter_dca_state positions:", json.dumps(zro, indent=2, ensure_ascii=False))
try:
    mark = float(client.futures_mark_price(symbol="ZROUSDT")["markPrice"])
    print(f"Mark: {mark}")
except Exception as e:
    print("Mark HATA:", e)
pos = state.get("positions", {}).get("merter_ei") or {}
if pos:
    avg = float(pos.get("avg_price") or pos.get("entry_price") or 0)
    tp1 = avg * 1.03
    tp2 = avg * 1.05
    print(f"avg={avg} tp1_done={pos.get('tp1_done')} tp2_done={pos.get('tp2_done')} trailing={pos.get('trailing_active')}")
    print(f"TP1 eşik={tp1:.6f} TP2 eşik={tp2:.6f} parts={pos.get('parts_filled')}/{pos.get('parts_total')}")
print("\nAçık limit emirler (ZROUSDT):")
orders = client.futures_get_open_orders(symbol="ZROUSDT")
if not orders:
    print("(açık emir yok)")
else:
    for o in orders:
        print(f"  {o.get('type')} {o.get('side')} qty={o.get('origQty')} price={o.get('price')} status={o.get('status')} id={o.get('orderId')}")

# --- SORU 3 signal_decisions BTC ETH ---
sep("SORU 3 — signal_decisions BTC/ETH 2026-06-04")
db = ROOT + "/mina_trading_journal.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()
rows = cur.execute("""
SELECT * FROM signal_decisions
WHERE date(created_at)='2026-06-04'
AND merter_symbol IN ('BTCUSDT','ETHUSDT')
ORDER BY created_at
""").fetchall()
if not rows:
    rows = cur.execute("""
    SELECT * FROM signal_decisions
    WHERE merter_symbol IN ('BTCUSDT','ETHUSDT')
    ORDER BY created_at DESC LIMIT 5
    """).fetchall()
for r in rows:
    print("-" * 40)
    for k in r.keys():
        print(f"  {k}: {r[k]}")
con.close()

# --- SORU 4 PDF ---
sep("SORU 4 — signals_log PDF/Haluk 2026-06-04")
import subprocess
r = subprocess.run(
    ["grep", "-iE", "pdf|haluk", ROOT + "/signal_bot/signals_log.txt"],
    capture_output=True, text=True
)
lines = [l for l in r.stdout.splitlines() if "2026-06-04" in l]
print("\n".join(lines) if lines else "(bugün PDF/Haluk satırı yok)")
pdf_dir = ROOT + "/signal_bot/pdfs"
if os.path.isdir(pdf_dir):
    pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf") and "20260604" in f])
    print("PDF dosyaları:", pdfs if pdfs else "(bugün pdf dosyası yok)")

# --- SORU 5 LABUSDT ---
sep("SORU 5 — LABUSDT hayalet kontrol")
for p in client.futures_position_information():
    if p["symbol"] != "LABUSDT":
        continue
    print(json.dumps(p, indent=2))
for fname in ["initial_entry_prices.json", "defense_levels.json", "initial_margins.json"]:
    data = json.load(open(ROOT + "/" + fname)) if os.path.isfile(ROOT + "/" + fname) else {}
    keys = [k for k in data if "LAB" in k.upper()]
    print(f"{fname} LAB keys: {keys or 'YOK'}")

# --- SORU 6 PARTI DERR ---
sep("SORU 6 — PARTI DERR")
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
rows = con.execute("SELECT * FROM trades WHERE symbol='PARTIUSDT'").fetchall()
print(f"PARTI trades count: {len(rows)}")
for r in rows:
    print(dict(r))
con.close()
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    path = f"{ROOT}/scripts/_bas_muhendis_query.py"
    with sftp.open(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, stdout, stderr = c.exec_command(f"{ROOT}/venv/bin/python {path}", timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    e = stderr.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()

if __name__ == "__main__":
    main()
