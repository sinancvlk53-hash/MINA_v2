# -*- coding: utf-8 -*-
"""
backtest_v2.py - EI Bot 1s LONG filtreli backtest (4 strateji)
Filtreler: Saat(09-11/15), Funding(<=0.03%), TREND(4h EMA50), S/R(4h ATR)
STR1: 3x Merter  STR2: 6x Sinan  STR3: 4x MINA  STR4: 3x Hizli
"""
import sys, os, json, time
from datetime import datetime, timezone
from collections import defaultdict

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv; load_dotenv(os.path.join(_ROOT, '.env'))
from config import BinanceConfig

OUT_FILE   = os.path.join(_ROOT, 'signal_bot/history/backtest_v2_results.json')
SAVE_EVERY = 50
TIMEOUT    = 24
VALID_HRS  = {9, 10, 15}
MAX_FR     = 0.0003
EMA_P      = 50
ATR_P      = 14

# ── Load ──────────────────────────────────────────────────────────────────────
ei = json.load(open(os.path.join(_ROOT, 'signal_bot/history/ei_signals.json'), encoding='utf-8'))
print(f'EI kayit: {len(ei)}')

cands = []
for rec in ei:
    if rec.get('timeframe') != '1s': continue
    for coin in rec.get('long_signals', []):
        cands.append({'ts': rec['timestamp'], 'coin': coin})
print(f'1s LONG: {len(cands)}')

cands = [c for c in cands if datetime.strptime(c['ts'], '%Y-%m-%d %H:%M').hour in VALID_HRS]
print(f'Saat filtresi: {len(cands)}')

# ── Indicators ────────────────────────────────────────────────────────────────
def calc_ema(vals, p=EMA_P):
    if len(vals) < p: return None
    e = sum(vals[:p]) / p
    m = 2 / (p + 1)
    for v in vals[p:]: e = v * m + e * (1 - m)
    return e

def calc_atr(ks, p=ATR_P):
    if len(ks) < p + 1: return None
    trs = []
    for i in range(1, len(ks)):
        h, l, pc = float(ks[i][2]), float(ks[i][3]), float(ks[i-1][4])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-p:]) / p

def swing_lows(ks, w=2):
    ls = [float(k[3]) for k in ks]
    n = len(ls)
    return [ls[i] for i in range(w, n - w)
            if all(ls[i] < ls[i-j] for j in range(1, w+1))
            and all(ls[i] < ls[i+j] for j in range(1, w+1))]

# ── API ───────────────────────────────────────────────────────────────────────
def to_ms(ts):
    return int(datetime.strptime(ts, '%Y-%m-%d %H:%M').replace(
               minute=0, second=0, tzinfo=timezone.utc).timestamp() * 1000)

def get_klines(client, sym, ivl, end=None, start=None, limit=70):
    for _ in range(3):
        try:
            kw = dict(symbol=sym, interval=ivl, limit=limit)
            if end:   kw['endTime']   = end
            if start: kw['startTime'] = start
            return client.futures_klines(**kw)
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e): return []
            time.sleep(1.5)
    return []

def get_funding(client, sym, ms):
    for _ in range(3):
        try:
            r = client.futures_funding_rate(symbol=sym, endTime=ms, limit=1)
            return float(r[-1]['fundingRate']) if r else None
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e): return None
            time.sleep(1.5)
    return None

# ── Strategies ────────────────────────────────────────────────────────────────
def extremes(k, entry):
    h, l = float(k[2]), float(k[3])
    return (l - entry) / entry * 100, (h - entry) / entry * 100

def sim_str1(ks):
    """3x: stop -2% coin, TP +4.6% coin"""
    if not ks or len(ks) < 2: return {'result': 'NO_DATA', 'roe': None, 'bars': 0}
    e = float(ks[0][4])
    for i, k in enumerate(ks[1:TIMEOUT+1], 1):
        w, b = extremes(k, e)
        if w <= -2.0: return {'result': 'LOSS', 'roe': -6.0,  'bars': i}
        if b >=  4.6: return {'result': 'WIN',  'roe': +13.8, 'bars': i}
    cp = (float(ks[min(TIMEOUT, len(ks)-1)][4]) - e) / e * 100
    return {'result': 'TIMEOUT', 'roe': round(cp * 3, 2), 'bars': TIMEOUT}

def sim_str2(ks):
    """6x: sim_stop -10%ROE, TP1 +3%ROE, TP2 +5%ROE"""
    if not ks or len(ks) < 2: return {'result': 'NO_DATA', 'roe': None, 'bars': 0}
    e = float(ks[0][4])
    sc, t1, t2 = -10/6, 3/6, 5/6
    tp1 = False
    for i, k in enumerate(ks[1:TIMEOUT+1], 1):
        w, b = extremes(k, e)
        if w <= sc: return {'result': 'LOSS',   'roe': -10.0, 'bars': i}
        if b >= t1: tp1 = True
        if tp1 and b >= t2: return {'result': 'WIN', 'roe': +5.0, 'bars': i}
    cp = (float(ks[min(TIMEOUT, len(ks)-1)][4]) - e) / e * 100
    return {'result': 'TP1_TO' if tp1 else 'TIMEOUT', 'roe': round(cp * 6, 2), 'bars': TIMEOUT}

def sim_str3(ks):
    """4x MINA: D1 -5%ROE (-1.25%coin), TP1 +3%ROE +0.75%coin (50%), TP2 +5%ROE +1.25%coin"""
    if not ks or len(ks) < 2: return {'result': 'NO_DATA', 'roe': None, 'bars': 0}
    e = float(ks[0][4])
    d1, t1, t2 = -5/4, 3/4, 5/4
    tp1 = False
    for i, k in enumerate(ks[1:TIMEOUT+1], 1):
        w, b = extremes(k, e)
        if w <= d1:
            if tp1: return {'result': 'D1_TP1', 'roe': round(1.5 + 0.5 * d1 * 4, 2), 'bars': i}
            return {'result': 'LOSS', 'roe': -5.0, 'bars': i}
        if b >= t1: tp1 = True
        if tp1 and b >= t2: return {'result': 'WIN', 'roe': +4.0, 'bars': i}
    cp = (float(ks[min(TIMEOUT, len(ks)-1)][4]) - e) / e * 100
    if tp1: return {'result': 'TP1_TO', 'roe': round(1.5 + 0.5 * cp * 4, 2), 'bars': TIMEOUT}
    return {'result': 'TIMEOUT', 'roe': round(cp * 4, 2), 'bars': TIMEOUT}

def sim_str4(ks):
    """3x hizli: stop -2%coin, TP1 +2%ROE +0.667%coin (50%), trailing -1%coin"""
    if not ks or len(ks) < 2: return {'result': 'NO_DATA', 'roe': None, 'bars': 0}
    e = float(ks[0][4])
    sc, t1c = -2.0, 2.0 / 3
    tp1 = False
    hi = 0.0
    for i, k in enumerate(ks[1:TIMEOUT+1], 1):
        w, b = extremes(k, e)
        if not tp1:
            if w <= sc: return {'result': 'LOSS', 'roe': -6.0, 'bars': i}
            if b >= t1c: tp1 = True; hi = b
        else:
            if b > hi: hi = b
            trail = hi - 1.0
            if w <= trail:
                return {'result': 'TRAIL', 'roe': round(1.0 + 0.5 * trail * 3, 2), 'bars': i}
    cp = (float(ks[min(TIMEOUT, len(ks)-1)][4]) - e) / e * 100
    if tp1: return {'result': 'TP1_TO', 'roe': round(1.0 + 0.5 * cp * 3, 2), 'bars': TIMEOUT}
    return {'result': 'TIMEOUT', 'roe': round(cp * 3, 2), 'bars': TIMEOUT}

# ── Backtest ──────────────────────────────────────────────────────────────────
cfg    = BinanceConfig()
client = cfg.get_client()
c4h, c1h, cfr = {}, {}, {}
results = []
skip    = defaultdict(int)
N       = len(cands)

for i, cand in enumerate(cands):
    ts   = cand['ts']
    coin = cand['coin']
    ms   = to_ms(ts)

    # Funding rate
    fr_key = (coin, ms // (8 * 3600 * 1000))
    if fr_key not in cfr:
        cfr[fr_key] = get_funding(client, coin, ms)
        time.sleep(0.05)
    fr = cfr[fr_key]
    if fr is not None and abs(fr) > MAX_FR:
        skip['FUNDING'] += 1; continue

    # 4h klines
    bkt4 = (coin, ms // (4 * 3600 * 1000))
    if bkt4 not in c4h:
        c4h[bkt4] = get_klines(client, coin, '4h', end=ms, limit=70)
        time.sleep(0.05)
    k4 = c4h[bkt4]
    if len(k4) < EMA_P + 2:
        skip['NO_4H'] += 1; continue

    ema_v = calc_ema([float(k[4]) for k in k4])
    atr_v = calc_atr(k4)
    if ema_v is None or atr_v is None:
        skip['NO_IND'] += 1; continue

    # 1h klines
    if (coin, ms) not in c1h:
        c1h[(coin, ms)] = get_klines(client, coin, '1h', start=ms, limit=TIMEOUT+2)
        time.sleep(0.05)
    k1 = c1h[(coin, ms)]
    if not k1 or len(k1) < 2:
        skip['NO_1H'] += 1; continue

    entry = float(k1[0][4])

    # TREND filter
    if entry <= ema_v:
        skip['TREND'] += 1; continue

    # S/R filter
    sups = [s for s in swing_lows(k4[-50:]) if s < entry]
    if not sups:
        skip['NO_SUP'] += 1; continue
    nearest = max(sups)
    if entry - nearest > atr_v:
        skip['FAR_SUP'] += 1; continue

    results.append({
        'ts':    ts,
        'coin':  coin,
        'entry': round(entry, 6),
        'ema50': round(ema_v, 6),
        'atr4h': round(atr_v, 6),
        'sup':   round(nearest, 6),
        'fr':    fr,
        'str1':  sim_str1(k1),
        'str2':  sim_str2(k1),
        'str3':  sim_str3(k1),
        'str4':  sim_str4(k1),
    })

    if (i + 1) % 200 == 0:
        print(f'  {i+1}/{N} - gecen: {len(results)}, atlanan: {dict(skip)}')

    if results and len(results) % SAVE_EVERY == 0:
        json.dump(results, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

json.dump(results, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# ── Summary ───────────────────────────────────────────────────────────────────
WIN_R = {
    'str1': {'WIN'},
    'str2': {'WIN', 'TP1_TO'},
    'str3': {'WIN', 'TP1_TO'},
    'str4': {'TRAIL', 'TP1_TO'},
}
LABELS = {
    'str1': '3x Merter (stop-2% TP+4.6%)',
    'str2': '6x Sinan  (simstop-10ROE TP1+3 TP2+5)',
    'str3': '4x MINA   (D1-5ROE TP1+3 TP2+5 50/50)',
    'str4': '3x Hizli  (stop-2% TP1+2ROE trail-1%)',
}

print(f'\nToplam aday : {N}')
print(f'Gecen filtre: {len(results)}')
print(f'Atlanan     : {dict(skip)}')
print(f'\n{"="*60}')
print(f'  BACKTEST V2 ({len(results)} islem)')
print(f'{"="*60}')

for st in ['str1', 'str2', 'str3', 'str4']:
    valid = [r for r in results if r[st]['result'] != 'NO_DATA']
    wins  = [r for r in valid if r[st]['result'] in WIN_R[st]]
    loss  = [r for r in valid if r[st]['result'] == 'LOSS']
    roes  = [r[st]['roe'] for r in valid if r[st]['roe'] is not None]
    wr    = len(wins) / (len(wins) + len(loss)) * 100 if (wins or loss) else 0
    avg   = sum(roes) / len(roes) if roes else 0
    cum   = sum(roes)
    stk = bst = 0
    for r in valid:
        if r[st]['result'] == 'LOSS': stk += 1; bst = max(bst, stk)
        else: stk = 0
    # Result distribution
    dist = {}
    for r in valid:
        res = r[st]['result']
        dist[res] = dist.get(res, 0) + 1
    print(f'\n  [{LABELS[st]}]')
    print(f'  N={len(valid)}  WIN={len(wins)}  LOSS={len(loss)}  dist={dist}')
    print(f'  Win Rate  : {wr:.1f}%')
    print(f'  Ort. ROE  : {avg:+.2f}%')
    print(f'  Kumulatif : {cum:+.1f}%')
    print(f'  Max kayip : {bst} islem')

print(f'\nKaydedildi: {OUT_FILE}')
