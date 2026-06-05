#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import re
from datetime import datetime

ROOT = "/root/MINA_v2"
TODAY = datetime.now().strftime("%Y-%m-%d")

def sep(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)

sep("MERTER DCA LOG — merter_ei_2")
for path in [f"{ROOT}/signal_bot/merter_dca.log", f"{ROOT}/signal_bot/merter_dca_filter.log"]:
    print(f"\n--- {path} ---")
    if not os.path.isfile(path):
        print("(dosya yok)")
        continue
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    ei2 = [l for l in lines if "merter_ei_2" in l or "EI süzgeçsiz" in l or "süzgeçsiz" in l.lower()]
    today_ei2 = [l for l in ei2 if TODAY in l]
    print(f"Toplam ei2/süzgeçsiz satır: {len(ei2)}, bugün: {len(today_ei2)}")
    for l in (today_ei2 or ei2)[-25:]:
        print(l)

sep("SIGNALS_LOG — bugün EI tarama")
sig_log = f"{ROOT}/signal_bot/signals_log.txt"
ei_msgs = []
merter_dispatch = []
if os.path.isfile(sig_log):
    for l in open(sig_log, encoding="utf-8", errors="replace"):
        if TODAY not in l:
            continue
        if "Yeni AL Sinyalleri" in l or "Sinyal Taraması" in l:
            ei_msgs.append(l.rstrip())
        if "merter_dca_manager" in l or "→ merter_dca" in l:
            merter_dispatch.append(l.rstrip())
    print(f"Bugün 'Yeni AL/Sinyal Taraması' içeren satır: {len(ei_msgs)}")
    for l in ei_msgs:
        print(l[:250])
    print(f"\nBugün merter_dca dispatch: {len(merter_dispatch)}")
    for l in merter_dispatch[-15:]:
        print(l[:250])
else:
    print("(signals_log yok)")

sep("merter_dca_state.json")
st = json.load(open(f"{ROOT}/signal_bot/merter_dca_state.json"))
print(json.dumps(st, indent=2, ensure_ascii=False))

sep("HALUK 22:38 — signals_log")
haluk_2238 = []
haluk_evening = []
if os.path.isfile(sig_log):
    for l in open(sig_log, encoding="utf-8", errors="replace"):
        line = l.rstrip()
        if "[HALUK]" not in line:
            continue
        if TODAY not in line:
            continue
        if "22:38" in line:
            haluk_2238.append(line)
        m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
        if m and m.group(1) >= f"{TODAY} 21:00:00":
            haluk_evening.append(line)
print(f"22:38 satırları: {len(haluk_2238)}")
for l in haluk_2238:
    print(l[:500])
print(f"\n21:00+ HALUK satırları: {len(haluk_evening)}")
for l in haluk_evening:
    print(l[:500])

sep("raw_signal_queue — haluk telegram")
qpath = f"{ROOT}/signal_bot/raw_signal_queue.json"
if os.path.isfile(qpath):
    q = json.load(open(qpath))
    entries = q.get("entries") or []
    for e in entries:
        ts = str(e.get("timestamp") or "")
        src = str(e.get("source") or "")
        if "haluk" not in src.lower():
            continue
        if TODAY in ts or "22:3" in ts:
            print(json.dumps(e, ensure_ascii=False, indent=2)[:1500])
    print("\n--- Son 8 haluk kayıt ---")
    haluk_all = [e for e in entries if "haluk" in str(e.get("source", "")).lower()]
    for e in haluk_all[-8:]:
        print(json.dumps({k: e.get(k) for k in ["timestamp", "source", "symbol", "direction", "status", "reject_reason", "entry_price"]}, ensure_ascii=False))

sep(f"TODAY={TODAY}")
