#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Sunucu sorguları: merter_ei_2, EI tarama, Haluk 22:38."""
import json
import os
import re
from datetime import datetime, timezone

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
ROOT = "/root/MINA_v2"

QUERY = r'''
import json, os, re
from datetime import datetime

ROOT = "/root/MINA_v2"
TODAY = datetime.now().strftime("%Y-%m-%d")

def sep(t):
    print("\n" + "="*72)
    print(t)
    print("="*72)

# --- merter logs ---
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

# --- EI tarama messages in signals_log ---
sep("SIGNALS_LOG — bugün EI tarama mesajları")
sig_log = f"{ROOT}/signal_bot/signals_log.txt"
if os.path.isfile(sig_log):
    lines = open(sig_log, encoding="utf-8", errors="replace").read().splitlines()
    ei_msgs = []
    for l in lines:
        if TODAY not in l:
            continue
        if "Yeni AL Sinyalleri" in l or "Sinyal Taraması" in l:
            ei_msgs.append(l)
        elif "[MERTER]" in l and ("EI" in l or "Tarama" in l or "merter_dca" in l):
            ei_msgs.append(l)
    print(f"Bugün EI ile ilgili satır: {len(ei_msgs)}")
    for l in ei_msgs[-30:]:
        print(l[:200])
else:
    print("(signals_log yok)")

# --- merter_dca_state ---
sep("merter_dca_state.json")
st = json.load(open(f"{ROOT}/signal_bot/merter_dca_state.json"))
print(json.dumps(st, indent=2, ensure_ascii=False)[:2000])

# --- Haluk 22:38 ---
sep("HALUK 22:38 — signals_log.txt")
target_h = "22:38"
haluk_lines = []
if os.path.isfile(sig_log):
    for l in open(sig_log, encoding="utf-8", errors="replace"):
        if TODAY not in l and "2026-06-04" not in l and "2026-06-02" not in l:
            continue
        if "[HALUK]" in l and target_h in l:
            haluk_lines.append(l.rstrip())
        elif "[HALUK]" in l and "22:3" in l:
            haluk_lines.append(l.rstrip())
print(f"22:3x HALUK satırları ({len(haluk_lines)}):")
for l in haluk_lines[:40]:
    print(l[:300])

# wider search haluk today evening
sep("HALUK bugün akşam (21:00+) signals_log")
evening = []
if os.path.isfile(sig_log):
    for l in open(sig_log, encoding="utf-8", errors="replace"):
        if TODAY not in l:
            continue
        if "[HALUK]" not in l:
            continue
        m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", l)
        if m:
            t = m.group(1)
            if t >= f"{TODAY} 21:00:00":
                evening.append(l.rstrip())
print(f"Satır: {len(evening)}")
for l in evening[-20:]:
    print(l[:350])

# --- raw_signal_queue haluk today ---
sep("raw_signal_queue.json — haluk/telegram bugün")
qpath = f"{ROOT}/signal_bot/raw_signal_queue.json"
if os.path.isfile(qpath):
    q = json.load(open(qpath))
    entries = q.get("entries") or []
    haluk_ent = []
    for e in entries:
        src = str(e.get("source", ""))
        ts = str(e.get("timestamp") or "")
        if "haluk" in src.lower() or src == "haluk_telegram":
            if TODAY in ts or "22:3" in ts:
                haluk_ent.append(e)
    # also last 15 haluk entries
    all_haluk = [e for e in entries if "haluk" in str(e.get("source","")).lower()]
    print(f"Bugün 22:3x haluk kayıt: {len(haluk_ent)}")
    for e in haluk_ent:
        print(json.dumps({k: e.get(k) for k in ["source","symbol","direction","status","reject_reason","timestamp","entry_price"]}, ensure_ascii=False))
    print(f"\nSon 10 haluk kayıt (tüm tarihler):")
    for e in all_haluk[-10:]:
        print(json.dumps({k: e.get(k) for k in ["source","symbol","direction","status","reject_reason","timestamp"]}, ensure_ascii=False))
else:
    print("(queue yok)")

sep("TODAY değişkeni: " + TODAY)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
_, o, e = c.exec_command(f"/root/MINA_v2/venv/bin/python -c {repr(QUERY)}", timeout=120)
# repr won't work well for multiline - upload script instead
c.close()
