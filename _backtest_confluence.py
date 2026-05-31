# -*- coding: utf-8 -*-
"""
Gecikmeli RSI+EI confluence backtesti
Giris: RSI <20 ateslenince 1-4 saat icinde gelen ilk EI LONG sinyali
"""
import sys, os, json, time
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding='utf-8')

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv; load_dotenv(os.path.join(_ROOT, '.env'))
from config import BinanceConfig

INTERVAL     = '1h'
TIMEOUT_BARS = 24

# ── Sinyal yukleme ────────────────────────────────────────────────────────────
ei  = json.load(open(os.path.join(_ROOT, 'signal_bot/history/ei_signals.json'),  encoding='utf-8'))
rsi = json.load(open(os.path.join(_ROOT, 'signal_bot/history/rsi_signals.json'), encoding='utf-8'))

ei_index = defaultdict(list)
for rec in ei:
    dt = datetime.strptime(rec['timestamp'], '%Y-%m-%d %H:%M')
    for coin in rec['long_signals']:
        ei_index[coin].append(dt)
for coin in ei_index:
    ei_index[coin].sort()

confluences = []
for rec in rsi:
    coin   = rec['coin']
    rsi_dt = datetime.strptime(rec['timestamp'], '%Y-%m-%d %H:%M')
    if coin not in ei_index:
        continue
    w_start = rsi_dt + timedelta(hours=1)
    w_end   = rsi_dt + timedelta(hours=4)
    for ei_dt in ei_index[coin]:
        if ei_dt < w_start: continue
        if ei_dt > w_end:   break
        confluences.append({
            'coin':      coin,
            'rsi_ts':    rec['timestamp'],
            'ei_ts':     ei_dt.strftime('%Y-%m-%d %H:%M'),
            'delay_min': int((ei_dt - rsi_dt).total_seconds() // 60),
            'rsi_5dk':   rec['rsi_5dk'],
            'rsi_15dk':  rec['rsi_15dk'],
        })
        break

print(f'{len(confluences)} confluence bulundu, backtest basliyor...')

# ── Strateji fonksiyonlari ────────────────────────────────────────────────────
def ts_to_ms(ts_str):
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M').replace(
             minute=0, second=0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def extremes(k, entry):
    h, l = float(k[2]), float(k[3])
    return (l - entry)/entry*100, (h - entry)/entry*100   # LONG only

def fetch(client, coin, start_ms):
    for _ in range(3):
        try:
            return client.futures_klines(symbol=coin, interval=INTERVAL,
                                          startTime=start_ms, limit=TIMEOUT_BARS+2)
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e): return []
            time.sleep(1.5)
    return []

def sim3x(klines):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'bars':0}
    entry = float(klines[0][4])
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = extremes(k, entry)
        if worst <= -2.0:
            return {'result':'LOSS', 'roe':-6.0,  'bars':i}
        if best  >=  4.6:
            return {'result':'WIN',  'roe':+13.8, 'bars':i}
    last = float(klines[min(TIMEOUT_BARS, len(klines)-1)][4])
    cp   = (last - entry)/entry*100
    return {'result':'TIMEOUT', 'roe':round(cp*3, 2), 'bars':TIMEOUT_BARS}

def sim6x(klines):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'bars':0}
    entry = float(klines[0][4])
    sc, t1c, t2c = -10/6, 3/6, 5/6
    tp1 = False
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = extremes(k, entry)
        if worst <= sc:
            return {'result':'LOSS', 'roe':-10.0, 'bars':i}
        if best >= t1c: tp1 = True
        if tp1 and best >= t2c:
            return {'result':'WIN',  'roe':+5.0, 'bars':i}
    last = float(klines[min(TIMEOUT_BARS, len(klines)-1)][4])
    cp   = (last - entry)/entry*100
    return {'result':'TP1_TIMEOUT' if tp1 else 'TIMEOUT', 'roe':round(cp*6,2), 'bars':TIMEOUT_BARS}

# ── Backtest ──────────────────────────────────────────────────────────────────
config = BinanceConfig()
client = config.get_client()
cache  = {}
results = []

for i, c in enumerate(confluences):
    ms  = ts_to_ms(c['ei_ts'])   # giris: EI sinyali aninda
    key = (c['coin'], ms)
    if key not in cache:
        cache[key] = fetch(client, c['coin'], ms)
        time.sleep(0.05)
    klines = cache[key]
    r3 = sim3x(klines)
    r6 = sim6x(klines)
    results.append({**c, '3x': r3, '6x': r6})
    if (i+1) % 30 == 0:
        print(f'  {i+1}/{len(confluences)}...')

# ── Ozet ──────────────────────────────────────────────────────────────────────
def stats(rows, strat):
    valid  = [r for r in rows if r[strat]['result'] != 'NO_DATA']
    wins   = [r for r in valid if r[strat]['result'] in ('WIN','TP1_TIMEOUT')]
    losses = [r for r in valid if r[strat]['result'] == 'LOSS']
    touts  = [r for r in valid if 'TIMEOUT' in r[strat]['result']]
    wr     = len(wins)/(len(wins)+len(losses))*100 if (wins or losses) else 0
    roes   = [r[strat]['roe'] for r in valid if r[strat]['roe'] is not None]
    avg    = sum(roes)/len(roes) if roes else 0
    cum    = sum(roes)
    # max kayip serisi
    streak = best = 0
    for r in valid:
        if r[strat]['result'] == 'LOSS': streak += 1; best = max(best, streak)
        else: streak = 0
    return {'total':len(valid),'wins':len(wins),'losses':len(losses),
            'timeouts':len(touts),'wr':wr,'avg':avg,'cum':cum,'max_streak':best}

print()
for strat in ['3x','6x']:
    s = stats(results, strat)
    print(f'== {strat} ================================================')
    print(f'  Toplam: {s["total"]}  WIN:{s["wins"]}  LOSS:{s["losses"]}  TIMEOUT:{s["timeouts"]}')
    print(f'  Win Rate    : {s["wr"]:.1f}%')
    print(f'  Ort. ROE    : {s["avg"]:+.2f}%')
    print(f'  Kumulatif   : {s["cum"]:+.1f}%')
    print(f'  Max kayip   : {s["max_streak"]} islem')
    print()

# En iyi coinler (min 5 islem)
print('En iyi coinler (min 5 islem, 3x ROE sirali):')
print(f'{"COIN":<18} {"N":>4}  {"WR3":>6} {"ROE3":>7}  {"WR6":>6} {"ROE6":>7}')
print('-'*55)
coin_rows = defaultdict(list)
for r in results: coin_rows[r['coin']].append(r)
coin_stats = []
for coin, rows in coin_rows.items():
    if len(rows) < 5: continue
    s3 = stats(rows,'3x'); s6 = stats(rows,'6x')
    coin_stats.append((coin, len(rows), s3['wr'], s3['avg'], s6['wr'], s6['avg']))
for row in sorted(coin_stats, key=lambda x: x[3], reverse=True):
    coin, n, wr3, ar3, wr6, ar6 = row
    print(f'{coin:<18} {n:>4}  {wr3:>5.1f}% {ar3:>+7.2f}%  {wr6:>5.1f}% {ar6:>+7.2f}%')

out = os.path.join(_ROOT, 'signal_bot/history/confluence_backtest.json')
json.dump(results, open(out,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'\nKaydedildi: {out}')
