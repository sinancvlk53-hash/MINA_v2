#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, sys, re, paramiko
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=25)
cmd = r"grep -E 'defense|take_profit|trailing' /root/MINA_v2/mina_bot.log | grep '2026-06-03' | sort"
_, out, err = c.exec_command(cmd, timeout=120)
data = out.read().decode('utf-8', errors='replace')
errdata = err.read().decode('utf-8', errors='replace')
print('=== HAM GREP CIKTISI ===')
print(data if data.strip() else '(bos)')
if errdata.strip():
    print('stderr:', errdata)
print(f'\n=== SATIR SAYISI: {len(data.splitlines()) if data else 0} ===')

# Ozet
counts = defaultdict(lambda: {'D1':0,'D2':0,'D3':0,'TP1':0,'TP2':0,'trailing':0,'other_defense':0})
sym_re = re.compile(r'INFO - (\w+) ')
for line in data.splitlines():
    m = sym_re.search(line)
    if not m:
        continue
    sym = m.group(1)
    ll = line.lower()
    if 'trailing' in ll:
        counts[sym]['trailing'] += 1
    elif "'level': 1" in line or "'level': 1," in line:
        counts[sym]['TP1'] += 1
    elif "'level': 2" in line or "'level': 2," in line:
        counts[sym]['TP2'] += 1
    elif "'defense_level': 1" in line:
        counts[sym]['D1'] += 1
    elif "'defense_level': 2" in line:
        counts[sym]['D2'] += 1
    elif "'defense_level': 3" in line:
        counts[sym]['D3'] += 1
    elif 'defense' in ll:
        counts[sym]['other_defense'] += 1

print('\n=== COIN BAZINDA OZET (2026-06-03) ===')
print(f"{'Coin':<14} {'D1':>4} {'D2':>4} {'D3':>4} {'TP1':>4} {'TP2':>4} {'Trail':>5}")
print('-' * 45)
for sym in sorted(counts.keys()):
    v = counts[sym]
    print(f"{sym:<14} {v['D1']:>4} {v['D2']:>4} {v['D3']:>4} {v['TP1']:>4} {v['TP2']:>4} {v['trailing']:>5}")
c.close()
