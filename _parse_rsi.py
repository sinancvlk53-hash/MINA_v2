# -*- coding: utf-8 -*-
import re, json, os

IN_FILE  = os.path.join(os.path.dirname(__file__), 'signal_bot', 'history', 'merter_history.txt')
OUT_FILE = os.path.join(os.path.dirname(__file__), 'signal_bot', 'history', 'rsi_signals.json')

# RSI(5dk): 17 | RSI(15dk): 18
RE_RSI   = re.compile(r'RSI\(5dk\):\s*(\d+).*?RSI\(15dk\):\s*(\d+)', re.IGNORECASE)
# [**NIGHTUSDT**] veya [NIGHTUSDT]
RE_COIN  = re.compile(r'\[\*{0,2}([A-Z0-9]+USDT)\*{0,2}\]')
# Funding Rate: -0.000045
RE_FUND  = re.compile(r'Funding Rate:\s*([-\d.]+)')
# Yon: <20 = LONG (oversold), >90 = SHORT (overbought)
RE_OVS   = re.compile(r'<20')
RE_OVB   = re.compile(r'>90')

results = []
skipped = 0

with open(IN_FILE, encoding='utf-8') as f:
    for line in f:
        if 'RSI Analizi' not in line:
            continue

        ts_m = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]', line)
        if not ts_m:
            skipped += 1; continue
        timestamp = ts_m.group(1)

        coin_m = RE_COIN.search(line)
        if not coin_m:
            skipped += 1; continue
        coin = coin_m.group(1)

        rsi_m = RE_RSI.search(line)
        if not rsi_m:
            skipped += 1; continue
        rsi5  = int(rsi_m.group(1))
        rsi15 = int(rsi_m.group(2))

        if RE_OVS.search(line):
            side = 'LONG'    # oversold <20
        elif RE_OVB.search(line):
            side = 'SHORT'   # overbought >90
        else:
            side = 'UNKNOWN'

        fund_m = RE_FUND.search(line)
        funding = float(fund_m.group(1)) if fund_m else None

        results.append({
            'timestamp':   timestamp,
            'coin':        coin,
            'rsi_5dk':     rsi5,
            'rsi_15dk':    rsi15,
            'side':        side,
            'funding_rate': funding,
        })

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

long_ct  = sum(1 for r in results if r['side'] == 'LONG')
short_ct = sum(1 for r in results if r['side'] == 'SHORT')
coins    = len(set(r['coin'] for r in results))

print(f'Toplam sinyal  : {len(results)}')
print(f'  LONG (<20)   : {long_ct}')
print(f'  SHORT (>90)  : {short_ct}')
print(f'  UNKNOWN      : {len(results)-long_ct-short_ct}')
print(f'Farkli coin    : {coins}')
print(f'Atlandı        : {skipped}')
print(f'Cikti          : {OUT_FILE}')
