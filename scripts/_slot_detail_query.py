#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from mina_ssh import connect_paramiko

REMOTE = r"""
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY'
from dotenv import load_dotenv
load_dotenv()
import os, sys, json
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client
from mina_slot_policy import (
    SLOT_TOTAL, SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR, MOTOR_SLOT_MAX,
    SLOTS_EI_DCA, SLOTS_MERTER_OTHER_DCA, MERTER_DCA_YUVAS,
)
from mina_manual_slot import count_motor_positions, count_merter_dca_used, merter_occupied_symbols

client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

motor_used = count_motor_positions(client)
merter_used = count_merter_dca_used()
merter_syms = merter_occupied_symbols()

print('=== SLOT OZET ===')
print(f'Toplam kasa slotu: {SLOT_TOTAL}')
print(f'Merter DCA yuvalari: {SLOTS_EI_DCA + SLOTS_MERTER_OTHER_DCA} (EI={SLOTS_EI_DCA}, other={SLOTS_MERTER_OTHER_DCA})')
print(f'Motor (4x): max {MOTOR_SLOT_MAX} (Haluk={SLOTS_HALUK_MOTOR}, Merter motor={SLOTS_MERTER_MOTOR})')
print(f'Merter DCA dolu: {merter_used}/{SLOTS_EI_DCA + SLOTS_MERTER_OTHER_DCA}')
print(f'Motor pozisyon dolu: {motor_used}/{MOTOR_SLOT_MAX}')
print(f'Motor bos slot: {MOTOR_SLOT_MAX - motor_used}')
print(f'Merter sembolleri (state): {sorted(merter_syms) or "yok"}')

try:
    with open('/root/MINA_v2/signal_bot/merter_dca_state.json') as f:
        st = json.load(f)
    pos = st.get('positions') or {}
    print('\n=== merter_dca_state yuvalar ===')
    for y in MERTER_DCA_YUVAS:
        p = pos.get(y)
        print(f'  {y}: {p.get("symbol") if p else "BOS"}')
except Exception as e:
    print('merter state:', e)

positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]
print('\n=== Acik pozisyonlar (motor sayimi) ===')
for p in positions:
    sym = p['symbol']
    lev = int(p.get('leverage') or 0)
    side = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    is_merter = sym in merter_syms and lev == 1 and side == 'LONG'
    bucket = 'Merter DCA' if is_merter else 'Motor (Haluk/PDF/HT)'
    print(f'  {sym} {side} {lev}x -> {bucket}')

orders = client.futures_get_open_orders()
from collections import defaultdict
by_sym = defaultdict(list)
for o in orders:
    by_sym[o['symbol']].append(o)
print('\n=== Bekleyen limit emirler (kaynak tahmini) ===')
pos_syms = {p['symbol'] for p in positions}
for sym in sorted(by_sym):
    n = len(by_sym[sym])
    lev_guess = 'Merter DCA (1x cok parca)' if n >= 3 else 'Haluk/PDF tek limit'
    has_pos = 'POZ VAR' if sym in pos_syms else 'poz yok'
    print(f'  {sym}: {n} emir [{lev_guess}] ({has_pos})')
PY
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, stdout, _ = c.exec_command(REMOTE, timeout=90)
sys.stdout.buffer.write(stdout.read())
c.close()
