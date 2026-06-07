# -*- coding: utf-8 -*-
import re
import json
import os

IN_FILE  = os.path.join(os.path.dirname(__file__), 'signal_bot', 'history', 'merter_history.txt')
OUT_FILE = os.path.join(os.path.dirname(__file__), 'signal_bot', 'history', 'ei_signals.json')

def extract_coins(text):
    return re.findall(r'\[([A-Z0-9]+USDT)\]', text)

def parse_block(timestamp, text):
    records = []

    # Split into timeframe sections
    # Sections start with "15 Dakikalık" or "1 Saatlik"
    tf_pattern = re.compile(r'(\d+\s*(?:Dakikalık|Saatlik))\s*Sinyaller[:\s]*(.*?)(?=\d+\s*(?:Dakikalık|Saatlik)\s*Sinyaller|Tarama Zamanı|$)', re.DOTALL)

    for m in tf_pattern.finditer(text):
        tf_raw  = m.group(1).strip()
        content = m.group(2)

        if '15' in tf_raw:
            timeframe = '15dk'
        elif '1' in tf_raw:
            timeframe = '1s'
        else:
            timeframe = tf_raw

        long_signals  = []
        short_signals = []

        al_m  = re.search(r'AL Sinyalleri[:\s]*(.*?)(?=SAT Sinyalleri|$)', content, re.DOTALL)
        sat_m = re.search(r'SAT Sinyalleri[:\s]*(.*?)$', content, re.DOTALL)

        if al_m:
            long_signals  = extract_coins(al_m.group(1))
        if sat_m:
            short_signals = extract_coins(sat_m.group(1))

        if long_signals or short_signals:
            records.append({
                'timestamp':     timestamp,
                'timeframe':     timeframe,
                'long_signals':  long_signals,
                'short_signals': short_signals,
            })

    return records

results = []
skipped = 0

with open(IN_FILE, encoding='utf-8') as f:
    for line in f:
        if 'EI Trading Bot' not in line:
            continue

        # Extract timestamp
        ts_m = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]', line)
        if not ts_m:
            skipped += 1
            continue
        timestamp = ts_m.group(1)

        # Extract body after channel tag
        body_m = re.search(r'\[MZTRADİNG GÜNCEL\]\s*(.*)', line)
        if not body_m:
            skipped += 1
            continue
        body = body_m.group(1)

        records = parse_block(timestamp, body)
        if not records:
            skipped += 1
        results.extend(records)

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

total_long  = sum(len(r['long_signals'])  for r in results)
total_short = sum(len(r['short_signals']) for r in results)

print(f"Toplam kayıt (timeframe bazlı): {len(results)}")
print(f"  15dk kayıt: {sum(1 for r in results if r['timeframe']=='15dk')}")
print(f"  1s  kayıt: {sum(1 for r in results if r['timeframe']=='1s')}")
print(f"Toplam LONG  sinyal: {total_long}")
print(f"Toplam SHORT sinyal: {total_short}")
print(f"Atlandı (parse edilemedi): {skipped}")
print(f"Çıktı: {OUT_FILE}")
