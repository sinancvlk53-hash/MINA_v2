# -*- coding: utf-8 -*-
"""
RSI tek basina backtest.
Giris: RSI <20 sinyali aninda coin kapanis fiyati.
Cikis: 3x (stop -%2, TP +%4.6) ve 6x (sim_stop -%10 ROE, TP1 +%3, TP2 +%5 ROE)
"""
import sys, os, json, time
from datetime import datetime, timezone
from collections import defaultdict, Counter
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv; load_dotenv(os.path.join(_ROOT, '.env'))
from config import BinanceConfig

INTERVAL     = '1h'
TIMEOUT_BARS = 24
OUT_FILE     = os.path.join(_ROOT, 'signal_bot/history/rsi_backtest.json')

rsi = json.load(open(os.path.join(_ROOT, 'signal_bot/history/rsi_signals.json'), encoding='utf-8'))
print(f'RSI sinyal sayisi: {len(rsi)}')

# ── Strateji ──────────────────────────────────────────────────────────────────
def ts_to_ms(ts_str):
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M').replace(
             minute=0, second=0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def extremes(k, entry, side):
    h, l = float(k[2]), float(k[3])
    if side == 'LONG':
        return (l - entry)/entry*100, (h - entry)/entry*100
    return (entry - h)/entry*100, (entry - l)/entry*100

def fetch(client, coin, start_ms):
    for _ in range(3):
        try:
            return client.futures_klines(symbol=coin, interval=INTERVAL,
                                          startTime=start_ms, limit=TIMEOUT_BARS+2)
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e): return []
            time.sleep(1.5)
    return []

def sim3x(klines, side):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'bars':0}
    entry = float(klines[0][4])
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = extremes(k, entry, side)
        if worst <= -2.0:
            return {'result':'LOSS','roe':-6.0,'bars':i}
        if best >= 4.6:
            return {'result':'WIN','roe':+13.8,'bars':i}
    last = float(klines[min(TIMEOUT_BARS, len(klines)-1)][4])
    cp   = (last - entry)/entry*100 if side=='LONG' else (entry - last)/entry*100
    return {'result':'TIMEOUT','roe':round(cp*3,2),'bars':TIMEOUT_BARS}

def sim6x(klines, side):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'bars':0}
    entry = float(klines[0][4])
    sc, t1c, t2c = -10/6, 3/6, 5/6
    tp1 = False
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = extremes(k, entry, side)
        if worst <= sc:
            return {'result':'LOSS','roe':-10.0,'bars':i}
        if best >= t1c: tp1 = True
        if tp1 and best >= t2c:
            return {'result':'WIN','roe':+5.0,'bars':i}
    last = float(klines[min(TIMEOUT_BARS, len(klines)-1)][4])
    cp   = (last - entry)/entry*100 if side=='LONG' else (entry - last)/entry*100
    return {'result':'TP1_TIMEOUT' if tp1 else 'TIMEOUT','roe':round(cp*6,2),'bars':TIMEOUT_BARS}

# ── Backtest ──────────────────────────────────────────────────────────────────
config = BinanceConfig()
client = config.get_client()
cache  = {}
results = []

for i, rec in enumerate(rsi):
    coin = rec['coin']
    ms   = ts_to_ms(rec['timestamp'])
    key  = (coin, ms)
    if key not in cache:
        cache[key] = fetch(client, coin, ms)
        time.sleep(0.05)
    klines = cache[key]
    side   = rec['side']   # hepsi LONG
    r3 = sim3x(klines, side)
    r6 = sim6x(klines, side)
    results.append({
        'timestamp': rec['timestamp'],
        'coin':      coin,
        'rsi_5dk':   rec['rsi_5dk'],
        'rsi_15dk':  rec['rsi_15dk'],
        'funding':   rec['funding_rate'],
        'side':      side,
        '3x':        r3,
        '6x':        r6,
    })
    if (i+1) % 200 == 0:
        print(f'  {i+1}/{len(rsi)}...')

json.dump(results, open(OUT_FILE,'w',encoding='utf-8'), ensure_ascii=False, indent=2)

# ── Ozet ──────────────────────────────────────────────────────────────────────
def summarize(rows, strat, label=''):
    valid  = [r for r in rows if r[strat]['result'] != 'NO_DATA']
    wins   = [r for r in valid if r[strat]['result'] in ('WIN','TP1_TIMEOUT')]
    losses = [r for r in valid if r[strat]['result'] == 'LOSS']
    touts  = [r for r in valid if 'TIMEOUT' in r[strat]['result']]
    wr     = len(wins)/(len(wins)+len(losses))*100 if (wins or losses) else 0
    roes   = [r[strat]['roe'] for r in valid if r[strat]['roe'] is not None]
    avg    = sum(roes)/len(roes) if roes else 0
    cum    = sum(roes)
    streak = best = 0
    for r in valid:
        if r[strat]['result'] == 'LOSS': streak += 1; best = max(best, streak)
        else: streak = 0
    print(f'\n  -- {strat} {label}--')
    print(f'  Toplam:{len(valid):5}  WIN:{len(wins):5}  LOSS:{len(losses):5}  TIMEOUT:{len(touts):5}')
    print(f'  Win Rate   : {wr:.1f}%')
    print(f'  Ort. ROE   : {avg:+.2f}%')
    print(f'  Kumulatif  : {cum:+.1f}%')
    print(f'  Max kayip  : {best} islem')
    return {'valid':len(valid),'wins':len(wins),'losses':len(losses),'wr':wr,'avg':avg,'cum':cum,'streak':best}

print(f'\n{"="*55}')
print(f'  RSI BACKTEST — GENEL ({len(results)} islem)')
print(f'{"="*55}')
for strat in ['3x','6x']:
    summarize(results, strat)

# Funding rate filtresi: riskli (Riskli) vs normal
no_fund  = [r for r in results if r['funding'] is None]
risk     = [r for r in results if r['funding'] is not None and abs(r['funding']) > 0.0003]
normal   = [r for r in results if r['funding'] is not None and abs(r['funding']) <= 0.0003]
print(f'\n{"="*55}')
print(f'  FUNDING RATE FİLTRESİ')
print(f'{"="*55}')
print(f'  Riskli funding (>0.03%): {len(risk)}')
print(f'  Normal funding:          {len(normal)}')
print(f'  Funding yok:             {len(no_fund)}')
for label, rows in [('Normal funding', normal), ('Riskli funding', risk)]:
    if not rows: continue
    print(f'\n  [{label}]')
    for strat in ['3x','6x']:
        summarize(rows, strat, f'({label}) ')

# En iyi coinler (min 10 islem)
print(f'\n{"="*55}')
print(f'  EN IYI COINLER (min 10 islem, 3x ROE sirali)')
print(f'{"="*55}')
print(f'{"COIN":<18} {"N":>4}  {"WR3":>6} {"ROE3":>7}  {"WR6":>6} {"ROE6":>7}')
print('-'*55)
coin_rows = defaultdict(list)
for r in results: coin_rows[r['coin']].append(r)
stats_list = []
for coin, rows in coin_rows.items():
    if len(rows) < 10: continue
    v3 = [r for r in rows if r['3x']['result']!='NO_DATA']
    v6 = [r for r in rows if r['6x']['result']!='NO_DATA']
    w3 = sum(1 for r in v3 if r['3x']['result']=='WIN')
    l3 = sum(1 for r in v3 if r['3x']['result']=='LOSS')
    w6 = sum(1 for r in v6 if r['6x']['result']=='WIN')
    l6 = sum(1 for r in v6 if r['6x']['result']=='LOSS')
    wr3 = w3/(w3+l3)*100 if (w3+l3) else 0
    wr6 = w6/(w6+l6)*100 if (w6+l6) else 0
    ar3 = sum(r['3x']['roe'] for r in v3 if r['3x']['roe'] is not None)/len(v3) if v3 else 0
    ar6 = sum(r['6x']['roe'] for r in v6 if r['6x']['roe'] is not None)/len(v6) if v6 else 0
    stats_list.append((coin, len(rows), wr3, ar3, wr6, ar6))
for row in sorted(stats_list, key=lambda x: x[3], reverse=True)[:20]:
    c, n, wr3, ar3, wr6, ar6 = row
    print(f'{c:<18} {n:>4}  {wr3:>5.1f}% {ar3:>+7.2f}%  {wr6:>5.1f}% {ar6:>+7.2f}%')

print(f'\nKaydedildi: {OUT_FILE}')
