# -*- coding: utf-8 -*-
"""
backtest_filtered.py — 3 filtreli backtest

Filtreler:
  1. BTC saatlik degisim < -1.5% → sinyali atla
  2. Ayni saatte 3+ coin → sadece ilkini al
  3. Sadece 8 altin coin + 1s sinyal + LONG

Kullanim:
  python backtest_filtered.py
"""
import os, sys, json, time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))
from binance.client import Client
from config import BinanceConfig

SIGNALS_FILE = os.path.join(_ROOT, 'signal_bot', 'history', 'ei_signals.json')
OUT_FILE     = os.path.join(_ROOT, 'signal_bot', 'history', 'backtest_filtered.json')
INTERVAL     = '1h'
TIMEOUT_BARS = 24

GOLDEN_COINS = {
    'PNUTUSDT','INJUSDT','TIAUSDT','ZKUSDT',
    'GMTUSDT','APTUSDT','CRVUSDT','JUPUSDT'
}

# ── Strateji fonksiyonlari (backtest.py ile ayni) ─────────────────────────────

def ts_to_ms(ts_str):
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M')
    dt = dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def candle_extremes(kline, side, entry):
    h, l = float(kline[2]), float(kline[3])
    if side == 'LONG':
        return (l - entry)/entry*100, (h - entry)/entry*100
    return (entry - h)/entry*100, (entry - l)/entry*100

def fetch_klines(client, coin, start_ms, limit=TIMEOUT_BARS+2):
    for _ in range(3):
        try:
            return client.futures_klines(symbol=coin, interval=INTERVAL,
                                          startTime=start_ms, limit=limit)
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e):
                return []
            time.sleep(1.5)
    return None

def simulate_3x(klines, side):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'entry':None,'exit_price':None,'bars':0}
    entry = float(klines[0][4])
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = candle_extremes(k, side, entry)
        if worst <= -2.0:
            ep = entry*(1-2/100) if side=='LONG' else entry*(1+2/100)
            return {'result':'LOSS','roe':-6.0,'entry':round(entry,6),'exit_price':round(ep,6),'bars':i}
        if best >= 4.6:
            ep = entry*(1+4.6/100) if side=='LONG' else entry*(1-4.6/100)
            return {'result':'WIN','roe':+13.8,'entry':round(entry,6),'exit_price':round(ep,6),'bars':i}
    last = float(klines[min(TIMEOUT_BARS,len(klines)-1)][4])
    cp   = (last-entry)/entry*100 if side=='LONG' else (entry-last)/entry*100
    return {'result':'TIMEOUT','roe':round(cp*3,2),'entry':round(entry,6),'exit_price':round(last,6),'bars':TIMEOUT_BARS}

def simulate_6x(klines, side):
    if not klines or len(klines) < 2:
        return {'result':'NO_DATA','roe':None,'entry':None,'exit_price':None,'bars':0}
    entry = float(klines[0][4])
    sc, t1c, t2c = -10/6, 3/6, 5/6
    tp1_hit = False
    for i, k in enumerate(klines[1:TIMEOUT_BARS+1], 1):
        worst, best = candle_extremes(k, side, entry)
        if worst <= sc:
            ep = entry*(1+sc/100) if side=='LONG' else entry*(1-sc/100)
            return {'result':'LOSS','roe':-10.0,'entry':round(entry,6),'exit_price':round(ep,6),'bars':i}
        if best >= t1c: tp1_hit = True
        if tp1_hit and best >= t2c:
            ep = entry*(1+t2c/100) if side=='LONG' else entry*(1-t2c/100)
            return {'result':'WIN','roe':+5.0,'entry':round(entry,6),'exit_price':round(ep,6),'bars':i}
    last = float(klines[min(TIMEOUT_BARS,len(klines)-1)][4])
    cp   = (last-entry)/entry*100 if side=='LONG' else (entry-last)/entry*100
    result = 'TP1_TIMEOUT' if tp1_hit else 'TIMEOUT'
    return {'result':result,'roe':round(cp*6,2),'entry':round(entry,6),'exit_price':round(last,6),'bars':TIMEOUT_BARS}

# ── BTC saatlik veri ──────────────────────────────────────────────────────────

def fetch_btc_hourly(client, signals):
    """Tum sinyal donemini kapsayan BTC 1h verisini cek."""
    ts_list = [s['timestamp'] for s in signals]
    min_ts  = min(ts_list)
    max_ts  = max(ts_list)
    start   = datetime.strptime(min_ts, '%Y-%m-%d %H:%M').replace(
                  minute=0, second=0, tzinfo=timezone.utc) - timedelta(hours=1)
    end     = datetime.strptime(max_ts, '%Y-%m-%d %H:%M').replace(
                  minute=0, second=0, tzinfo=timezone.utc) + timedelta(hours=2)

    start_ms = int(start.timestamp()*1000)
    end_ms   = int(end.timestamp()*1000)

    btc_map = {}   # start_ms_of_candle -> pct_change_vs_prev_close
    prev_close = None
    cursor = start_ms

    print("BTC saatlik veri cekiliyor...")
    while cursor < end_ms:
        batch = client.futures_klines(symbol='BTCUSDT', interval='1h',
                                       startTime=cursor, limit=500)
        if not batch:
            break
        for k in batch:
            c = float(k[4])
            o = float(k[1])
            if prev_close is not None:
                pct = (c - prev_close) / prev_close * 100
            else:
                pct = 0.0
            btc_map[k[0]] = {'pct': pct, 'open': o, 'close': c}
            prev_close = c
        cursor = batch[-1][0] + 3600000
        time.sleep(0.1)

    print(f"BTC verisi: {len(btc_map)} mum")
    return btc_map


def btc_pct_at(btc_map, ts_str):
    """Verilen timestamp icin BTC saatlik degisimini dondur."""
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M').replace(
             minute=0, second=0, tzinfo=timezone.utc)
    ms = int(dt.timestamp()*1000)
    return btc_map.get(ms, {}).get('pct', 0.0)

# ── Ozet ──────────────────────────────────────────────────────────────────────

def summarize(label, results):
    print(f"\n{'='*50}")
    print(f"  {label}  ({len(results)} islem)")
    print(f"{'='*50}")
    for strat in ['3x','6x']:
        valid    = [r for r in results if r[strat]['result'] != 'NO_DATA']
        wins     = [r for r in valid if r[strat]['result'] in ('WIN','TP1_TIMEOUT')]
        losses   = [r for r in valid if r[strat]['result'] == 'LOSS']
        timeouts = [r for r in valid if 'TIMEOUT' in r[strat]['result']]
        wr  = len(wins)/(len(wins)+len(losses))*100 if (wins or losses) else 0
        avg = sum(r[strat]['roe'] for r in valid if r[strat]['roe'] is not None)/len(valid) if valid else 0
        cum = sum(r[strat]['roe'] for r in valid if r[strat]['roe'] is not None)
        print(f"\n  -- {strat} --")
        print(f"  WIN:{len(wins):4}  LOSS:{len(losses):4}  TIMEOUT:{len(timeouts):4}  WR:{wr:.1f}%")
        print(f"  Ort ROE:{avg:+.2f}%  |  Kumulatif:{cum:+.1f}%")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    config = BinanceConfig()
    client = config.get_client()

    with open(SIGNALS_FILE, encoding='utf-8') as f:
        signals = json.load(f)

    # Filtre 3: 1s + LONG + altin coin
    signals_f3 = [s for s in signals if s['timeframe'] == '1s']
    for s in signals_f3:
        s['long_signals']  = [c for c in s['long_signals']  if c in GOLDEN_COINS]
        s['short_signals'] = []
    signals_f3 = [s for s in signals_f3 if s['long_signals']]

    print(f"Filtre 3 sonrasi: {len(signals_f3)} sinyal kaydi")

    # BTC verisi
    btc_map = fetch_btc_hourly(client, signals_f3)

    # Filtre 1 + 2 uygula, islem listesi olustur
    trades = []
    skipped_btc = 0
    skipped_dup = 0

    hour_counts = defaultdict(int)   # Filtre 2: saat bazli sayac

    for sig in signals_f3:
        ts   = sig['timestamp']
        hour = ts[:13]   # 'YYYY-MM-DD HH'

        # Filtre 1: BTC saatlik degisim
        btc_pct = btc_pct_at(btc_map, ts)
        if btc_pct < -1.5:
            skipped_btc += len(sig['long_signals'])
            continue

        for coin in sig['long_signals']:
            # Filtre 2: ayni saatte 3+ coin
            if hour_counts[hour] >= 1:   # ilkinden sonrakileri atla
                skipped_dup += 1
                continue
            hour_counts[hour] += 1
            trades.append({'ts': ts, 'coin': coin, 'btc_pct': round(btc_pct, 2)})

    print(f"BTC filtresi ile atlanan: {skipped_btc} islem")
    print(f"Duplikat filtresi ile atlanan: {skipped_dup} islem")
    print(f"Kalan islem: {len(trades)}")

    # Backtest
    results = []
    kline_cache = {}

    for i, t in enumerate(trades):
        start_ms  = ts_to_ms(t['ts'])
        cache_key = (t['coin'], start_ms)

        if cache_key not in kline_cache:
            kline_cache[cache_key] = fetch_klines(client, t['coin'], start_ms)
            time.sleep(0.05)

        klines = kline_cache[cache_key]
        r3 = simulate_3x(klines, 'LONG')
        r6 = simulate_6x(klines, 'LONG')

        results.append({
            'timestamp': t['ts'],
            'coin':      t['coin'],
            'btc_pct':   t['btc_pct'],
            '3x':        r3,
            '6x':        r6,
        })

        if (i+1) % 10 == 0:
            print(f"  {i+1}/{len(trades)} islem...")

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Karsilastirma
    # Filtresiz baseline (backtest_results.json'dan 8 coin + 1s + LONG)
    base = json.load(open(
        os.path.join(_ROOT, 'signal_bot', 'history', 'backtest_results.json'),
        encoding='utf-8'))
    baseline = [r for r in base
                if r['coin'] in GOLDEN_COINS
                and r['side'] == 'LONG'
                and r['timeframe'] == '1s'
                and r['3x']['result'] != 'NO_DATA']

    summarize("BASELINE (filtresiz)", baseline)
    summarize("FILTRELI (BTC + duplikat)", results)

    print(f"\nKaydedildi: {OUT_FILE}")

if __name__ == '__main__':
    main()
