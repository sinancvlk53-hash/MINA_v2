# -*- coding: utf-8 -*-
"""Anlık pozisyon snapshot + log özeti"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from datetime import datetime

ROOT         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LOG_FILE     = os.path.join(ROOT, 'mina_bot.log')
DEFENSE_FILE = os.path.join(ROOT, 'defense_levels.json')
INITIAL_FILE = os.path.join(ROOT, 'initial_margins.json')
TP_FILE      = os.path.join(ROOT, 'tp_levels.json')
ALERT_ROE    = -70.0

def load_json(path):
    try:
        with open(path) as f: return json.load(f)
    except: return {}

def parse_log():
    events = {'D1':[], 'D2':[], 'D3_ok':[], 'D3_fail':[], 'TP1':[], 'TP2':[], 'SL':[], 'TRAILING':[], 'ERR':[]}
    try:
        with open(LOG_FILE, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if 'SAVUNMA 1' in line and 'eklendi' in line: events['D1'].append(line)
                elif 'SAVUNMA 2' in line and 'eklendi' in line: events['D2'].append(line)
                elif 'SAVUNMA 3' in line and 'MARGIN eklendi' in line: events['D3_ok'].append(line)
                elif ('SAVUNMA 3' in line or '-4054' in line) and ('BAŞARISIZ' in line or 'HATASI' in line or 'MARGIN HATASI' in line): events['D3_fail'].append(line)
                elif 'TP1' in line: events['TP1'].append(line)
                elif 'TP2' in line: events['TP2'].append(line)
                elif 'TRAILING' in line and 'kapatıldı' in line: events['TRAILING'].append(line)
                elif 'STOP LOSS' in line and 'kapatıldı' in line: events['SL'].append(line)
                elif 'ERROR' in line or ('HATA' in line and 'MARGIN' not in line): events['ERR'].append(line)
    except: pass
    return events

print('═'*65, flush=True)
print(f'  MİNA v2 — ANLIKKK RAPOR  {datetime.now().strftime("%H:%M:%S")}', flush=True)
print('═'*65, flush=True)

# ── LOG ÖZETİ ───────────────────────────────────────────────────────────
events = parse_log()
print('\n📋 LOG ÖZETI (tüm oturumlar):', flush=True)
print(f'   D1 tetiklemeler  : {len(events["D1"])}', flush=True)
print(f'   D2 tetiklemeler  : {len(events["D2"])}', flush=True)
print(f'   D3 BAŞARILI      : {len(events["D3_ok"])}', flush=True)
print(f'   D3 BAŞARISIZ     : {len(events["D3_fail"])}', flush=True)
print(f'   TP1 tetiklemeler : {len(events["TP1"])}', flush=True)
print(f'   TP2 tetiklemeler : {len(events["TP2"])}', flush=True)
print(f'   TRAILING kapatma : {len(events["TRAILING"])}', flush=True)
print(f'   SL tetiklemeler  : {len(events["SL"])}', flush=True)
print(f'   Hatalar          : {len(events["ERR"])}', flush=True)

if events['D3_fail']:
    print('\n🚨 D3 BAŞARISIZ SATIRLAR:', flush=True)
    for l in events['D3_fail']: print(f'   {l}', flush=True)

if events['D3_ok']:
    print('\n✅ D3 BAŞARILI SATIRLAR:', flush=True)
    for l in events['D3_ok']: print(f'   {l}', flush=True)

# ── POZİSYONLAR ─────────────────────────────────────────────────────────
config  = BinanceConfig()
client  = config.get_client()

bal_data = client.futures_account_balance()
balance  = float(next(x for x in bal_data if x['asset']=='USDT')['balance'])
slot_size = balance / 10

defense_lvls = load_json(DEFENSE_FILE)
init_margins = load_json(INITIAL_FILE)
tp_lvls      = load_json(TP_FILE)

positions = client.futures_position_information()
open_pos  = [p for p in positions if float(p['positionAmt']) != 0]

print(f'\n💰 Bakiye: {balance:.2f} USDT  |  Slot: {slot_size:.2f} USDT', flush=True)
print(f'📊 Açık Pozisyon: {len(open_pos)}\n', flush=True)

print(f'  {"Coin":<12} {"Side":<6} {"Lev":>4}  {"ROE":>9}  {"PnL":>10}  {"Margin":>9}  {"D":>2}  {"TP":>3}  {"Uyarı"}', flush=True)
print(f'  {"─"*12} {"─"*6} {"─"*4}  {"─"*9}  {"─"*10}  {"─"*9}  {"─"*2}  {"─"*3}  {"─"*12}', flush=True)

warnings = []
for p in open_pos:
    symbol  = p['symbol']
    side    = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    lev     = int(p['leverage'])
    upnl    = float(p['unRealizedProfit'])
    iso_mrg = float(p['isolatedMargin'])
    pos_key = f"{symbol}_{side}"

    init_m = init_margins.get(pos_key, iso_mrg)
    roe    = (upnl / init_m * 100) if init_m > 0 else 0.0
    d_lvl  = defense_lvls.get(pos_key, 0)
    tp_lvl = tp_lvls.get(pos_key, 0)

    warn = ''
    if roe <= ALERT_ROE:
        warn = '🔴LİKİDASYON!'
        warnings.append(f'🚨 {symbol} {side} ROE={roe:.1f}%')
    elif iso_mrg > slot_size:
        warn = '⚠️ LİMİT AŞTI'
        warnings.append(f'⚠️ {symbol} {side} margin={iso_mrg:.1f} > slot={slot_size:.1f}')

    roe_icon = '🟢' if roe >= 0 else ('🔴' if roe <= ALERT_ROE else ('🟠' if roe < -30 else '🟡'))
    print(f'  {symbol:<12} {side:<6} {lev:>4}x  {roe_icon}{roe:>+7.2f}%  {upnl:>+10.2f}$  {iso_mrg:>8.2f}$  {d_lvl:>2}  {tp_lvl:>3}  {warn}', flush=True)

total = sum(float(p['unRealizedProfit']) for p in open_pos)
print(f'\n  Toplam PnL: {total:+.2f} USDT', flush=True)

if warnings:
    print('\n' + '!'*65, flush=True)
    for w in warnings: print(f'  {w}', flush=True)
    print('!'*65, flush=True)

# ── Son log satırları ──────────────────────────────────────────────────
print('\n📝 SON 10 LOG SATIRI:', flush=True)
try:
    with open(LOG_FILE, encoding='utf-8', errors='replace') as f:
        lines = [l.strip() for l in f if l.strip()]
    for l in lines[-10:]: print(f'   {l}', flush=True)
except: print('   Log okunamadı', flush=True)

print('\n' + '═'*65, flush=True)
