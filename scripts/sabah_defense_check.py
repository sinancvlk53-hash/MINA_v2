#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabah defense logları + SOL/LINK/INJ D1 eşik kontrolü."""
import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"

CMD = r"""
echo '========== DEFENSE LOG 2026-06-04 =========='
grep -E 'defense' /root/MINA_v2/mina_bot.log 2>/dev/null | grep '2026-06-04' || echo '(kayıt yok)'

echo ''
echo '========== D1 EŞİK + MARK (SOL/LINK/INJ) =========='
cd /root/MINA_v2
/root/MINA_v2/venv/bin/python - <<'PY'
import json, os, sys
sys.path.insert(0, "/root/MINA_v2")
from dotenv import load_dotenv
load_dotenv("/root/MINA_v2/.env")

ROWS = [
    ("SOLUSDT", "LONG"),
    ("LINKUSDT", "LONG"),
    ("INJUSDT", "LONG"),
]
D1_MULT = 0.95

def load_json(name):
    p = os.path.join("/root/MINA_v2", name)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)

initial = load_json("initial_entry_prices.json")
defense = load_json("defense_levels.json")
syms = [s for s, _ in ROWS]

marks = {}
try:
    import requests
    r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=10)
    for row in r.json():
        s = row.get("symbol")
        if s in syms:
            marks[s] = float(row.get("markPrice", 0))
except Exception as e:
    print(f"mark fiyat alınamadı: {e}")

print(f"{'KEY':<18} {'initial_entry':>14} {'D1 eşik (×0.95)':>16} {'mark':>14} {'altında?':>10} {'def_lvl':>8} {'D1 tetik?':>10}")
print("-" * 95)
for sym, side in ROWS:
    key = f"{sym}_{side}"
    entry = initial.get(key)
    try:
        entry_f = float(entry) if entry is not None else None
    except (TypeError, ValueError):
        entry_f = None
    d1 = entry_f * D1_MULT if entry_f else None
    mark = marks.get(sym)
    below = mark <= d1 if (d1 is not None and mark is not None) else None
    lvl = int(defense.get(key, 0))
    triggered = "EVET (geçmiş)" if lvl >= 1 else ("EVET (şimdi)" if below else "HAYIR")
    ie = f"{entry_f:.6f}" if entry_f else "—"
    d1s = f"{d1:.6f}" if d1 else "—"
    ms = f"{mark:.6f}" if mark is not None else "—"
    bs = "EVET" if below is True else ("HAYIR" if below is False else "—")
    print(f"{key:<18} {ie:>14} {d1s:>16} {ms:>14} {bs:>10} {lvl:>8} {triggered:>10}")

print()
print("D1 kuralı (LONG): mark <= initial_entry × 0.95")
print("defense_levels:", {f"{s}_{d}": defense.get(f"{s}_{d}", 0) for s, d in ROWS})
PY
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    stdin, stdout, stderr = c.exec_command(CMD, timeout=90)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    c.close()

if __name__ == "__main__":
    main()
