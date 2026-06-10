#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
echo "========== 1. slot policy grep =========="
grep -rn "SLOTS_HALUK\|SLOTS_MERTER\|slot_policy\|HT_SLOTS\|MOTOR_SLOT" /root/MINA_v2/ --include="*.py" 2>/dev/null | grep -v venv | head -25

echo ""
echo "========== 2-3. Emirler + pozisyonlar + slot analizi =========="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys
from collections import Counter
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client

client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

orders = client.futures_get_open_orders()
symbols = Counter(o['symbol'] for o in orders)
print('Emir sayisi per coin:', dict(symbols))
print('Toplam emir:', len(orders))

positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
print(f'\nAcik pozisyon: {len(positions)}')
for p in positions:
    side = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    print(f"  {p['symbol']} {side} amt={p['positionAmt']}")

# Slot policy
try:
    from mina_slot_policy import get_slot_limits, count_used_slots, describe_slot_budget
    limits = get_slot_limits()
    used = count_used_slots(client)
    print('\n--- Slot policy ---')
    for k, v in limits.items():
        print(f'  {k}: {v}')
    print(f'  used_total: {used}')
    if hasattr(describe_slot_budget, '__call__'):
        print('  budget:', describe_slot_budget(client))
except Exception as e:
    print('\nSlot policy import hatasi:', e)
    try:
        from mina_dashboard_settings import load_settings
        s = load_settings()
        print('  dashboard slots:', {k: s.get(k) for k in s if 'slot' in k.lower()})
    except Exception as e2:
        print('  settings:', e2)

# Coins with orders but no position
pos_syms = {p['symbol'] for p in positions}
order_syms = {o['symbol'] for o in orders}
pending_only = order_syms - pos_syms
print(f'\nEmir var pozisyon yok ({len(pending_only)} coin):', sorted(pending_only))
for sym in sorted(pending_only):
    sym_orders = [o for o in orders if o['symbol'] == sym]
    print(f'  {sym}: {len(sym_orders)} emir')
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, stderr = c.exec_command(REMOTE, timeout=90)
sys.stdout.buffer.write(stdout.read())
err = stderr.read().decode('utf-8', errors='replace')
if err.strip():
    sys.stdout.buffer.write(('\nSTDERR: ' + err).encode('utf-8', errors='replace'))
c.close()
