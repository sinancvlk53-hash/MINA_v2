# -*- coding: utf-8 -*-
"""
backtest.py — EI Trading Bot sinyal backtesti

Kullanım:
  python backtest.py 10          # ilk 10 sinyal kaydını test et
  python backtest.py             # tümünü çalıştır

Giriş:  signal_bot/history/ei_signals.json
Çıktı:  signal_bot/history/backtest_results.json
"""
import os, sys, json, time
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from binance.client import Client
from config import BinanceConfig

SIGNALS_FILE = os.path.join(_ROOT, 'signal_bot', 'history', 'ei_signals.json')
OUT_FILE     = os.path.join(_ROOT, 'signal_bot', 'history', 'backtest_results.json')

INTERVAL     = '1h'
TIMEOUT_BARS = 24    # 24 saat

# ── Yardımcı ──────────────────────────────────────────────────────────────────

def ts_to_ms(ts_str: str) -> int:
    """'2026-05-03 22:15' → saat başına yuvarlanmış UTC ms"""
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M')
    dt = dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def candle_extremes(kline, side: str, entry: float):
    """Her mum için en kötü ve en iyi coin % hareketini döndür."""
    h, l = float(kline[2]), float(kline[3])
    if side == 'LONG':
        worst = (l - entry) / entry * 100   # negatif = kötü
        best  = (h - entry) / entry * 100   # pozitif = iyi
    else:  # SHORT
        worst = (entry - h) / entry * 100   # negatif = kötü (fiyat yükseldi)
        best  = (entry - l) / entry * 100   # pozitif = iyi (fiyat düştü)
    return worst, best


def fetch_klines(client, coin: str, start_ms: int) -> list | None:
    for attempt in range(3):
        try:
            return client.futures_klines(
                symbol=coin,
                interval=INTERVAL,
                startTime=start_ms,
                limit=TIMEOUT_BARS + 2,
            )
        except Exception as e:
            if 'Invalid symbol' in str(e) or '-1121' in str(e):
                return []        # coin artık listede yok
            time.sleep(1.5)
    return None


# ── Strateji: 3x ──────────────────────────────────────────────────────────────
# stop: coin -%2  |  TP1: coin +%4.6
# Giriş: sinyal mumunun kapanış fiyatı

def simulate_3x(klines: list, side: str) -> dict:
    if not klines or len(klines) < 2:
        return {'result': 'NO_DATA', 'roe': None, 'entry': None, 'exit_price': None, 'bars': 0}

    entry = float(klines[0][4])   # sinyal mumunun close'u
    lev   = 3
    stop  = -2.0    # coin %
    tp1   = 4.6     # coin %

    for i, k in enumerate(klines[1:TIMEOUT_BARS + 1], 1):
        worst, best = candle_extremes(k, side, entry)
        if worst <= stop:
            exit_p = entry * (1 + stop / 100) if side == 'LONG' else entry * (1 - stop / 100)
            return {'result': 'LOSS', 'roe': round(stop * lev, 2),
                    'entry': round(entry, 6), 'exit_price': round(exit_p, 6), 'bars': i}
        if best >= tp1:
            exit_p = entry * (1 + tp1 / 100) if side == 'LONG' else entry * (1 - tp1 / 100)
            return {'result': 'WIN', 'roe': round(tp1 * lev, 2),
                    'entry': round(entry, 6), 'exit_price': round(exit_p, 6), 'bars': i}

    last_c   = float(klines[min(TIMEOUT_BARS, len(klines) - 1)][4])
    coin_pct = (last_c - entry) / entry * 100 if side == 'LONG' else (entry - last_c) / entry * 100
    return {'result': 'TIMEOUT', 'roe': round(coin_pct * lev, 2),
            'entry': round(entry, 6), 'exit_price': round(last_c, 6), 'bars': TIMEOUT_BARS}


# ── Strateji: 6x ──────────────────────────────────────────────────────────────
# sim_stop: ROE -%10  |  TP1: ROE +%3  |  TP2: ROE +%5
# coin eşdeğerleri: stop=-1.667%  tp1=0.5%  tp2=0.833%

def simulate_6x(klines: list, side: str) -> dict:
    if not klines or len(klines) < 2:
        return {'result': 'NO_DATA', 'roe': None, 'entry': None, 'exit_price': None, 'bars': 0}

    entry    = float(klines[0][4])
    lev      = 6
    stop_roe = -10.0
    tp1_roe  =   3.0
    tp2_roe  =   5.0
    stop_c   = stop_roe / lev    # -1.6667%
    tp1_c    = tp1_roe  / lev    #  0.5%
    tp2_c    = tp2_roe  / lev    #  0.8333%

    tp1_hit = False

    for i, k in enumerate(klines[1:TIMEOUT_BARS + 1], 1):
        worst, best = candle_extremes(k, side, entry)

        if worst <= stop_c:
            exit_p = entry * (1 + stop_c / 100) if side == 'LONG' else entry * (1 - stop_c / 100)
            return {'result': 'LOSS', 'roe': round(stop_roe, 2),
                    'entry': round(entry, 6), 'exit_price': round(exit_p, 6), 'bars': i}

        if best >= tp1_c:
            tp1_hit = True

        if tp1_hit and best >= tp2_c:
            exit_p = entry * (1 + tp2_c / 100) if side == 'LONG' else entry * (1 - tp2_c / 100)
            return {'result': 'WIN', 'roe': round(tp2_roe, 2),
                    'entry': round(entry, 6), 'exit_price': round(exit_p, 6), 'bars': i}

    last_c   = float(klines[min(TIMEOUT_BARS, len(klines) - 1)][4])
    coin_pct = (last_c - entry) / entry * 100 if side == 'LONG' else (entry - last_c) / entry * 100
    result   = 'TP1_TIMEOUT' if tp1_hit else 'TIMEOUT'
    return {'result': result, 'roe': round(coin_pct * lev, 2),
            'entry': round(entry, 6), 'exit_price': round(last_c, 6), 'bars': TIMEOUT_BARS}


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def print_summary(results: list):
    for strat in ['3x', '6x']:
        valid    = [r for r in results if r[strat]['result'] != 'NO_DATA']
        wins     = [r for r in valid if r[strat]['result'] in ('WIN', 'TP1_TIMEOUT')]
        losses   = [r for r in valid if r[strat]['result'] == 'LOSS']
        timeouts = [r for r in valid if 'TIMEOUT' in r[strat]['result']]
        wr       = len(wins) / (len(wins) + len(losses)) * 100 if (wins or losses) else 0
        avg_roe  = (sum(r[strat]['roe'] for r in valid if r[strat]['roe'] is not None)
                    / len(valid)) if valid else 0
        print(f"\n-- {strat} ----------------------------------")
        print(f"  Toplam  : {len(valid)}")
        print(f"  WIN     : {len(wins)}")
        print(f"  LOSS    : {len(losses)}")
        print(f"  TIMEOUT : {len(timeouts)}")
        print(f"  Win Rate: {wr:.1f}%  (WIN/LOSS dışı TIMEOUT sayılmaz)")
        print(f"  Ort. ROE: {avg_roe:+.2f}%")


def main(limit=None):
    config = BinanceConfig()
    client = config.get_client()

    with open(SIGNALS_FILE, encoding='utf-8') as f:
        signals = json.load(f)

    if limit:
        signals = signals[:limit]

    total_signals = len(signals)
    print(f"Backtest başlıyor: {total_signals} sinyal kaydı "
          f"({'tümü' if not limit else f'ilk {limit}'})")

    results    = []
    kline_cache = {}   # (coin, start_ms) → klines

    for idx, sig in enumerate(signals):
        ts       = sig['timestamp']
        tf       = sig['timeframe']
        start_ms = ts_to_ms(ts)

        all_coins = (
            [(c, 'LONG')  for c in sig['long_signals']] +
            [(c, 'SHORT') for c in sig['short_signals']]
        )

        for coin, side in all_coins:
            cache_key = (coin, start_ms)
            if cache_key not in kline_cache:
                klines = fetch_klines(client, coin, start_ms)
                kline_cache[cache_key] = klines
                time.sleep(0.05)

            klines = kline_cache[cache_key]

            r3 = simulate_3x(klines, side)
            r6 = simulate_6x(klines, side)

            results.append({
                'timestamp': ts,
                'timeframe': tf,
                'coin':      coin,
                'side':      side,
                '3x':        r3,
                '6x':        r6,
            })

        if (idx + 1) % 50 == 0:
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  {idx + 1}/{total_signals} sinyal islendi, "
                  f"{len(results)} islem kaydedildi...")

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{len(results)} islem kaydedildi: {OUT_FILE}")
    print_summary(results)


if __name__ == '__main__':
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=lim)
