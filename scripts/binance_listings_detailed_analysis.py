#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Son N günde Binance USDT-M listelemeleri — 1s/4s max yükseliş, zirve sonrası düşüş."""
import os
import sys
import time
import statistics as st

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from signal_bot.binance_listings import build_recent_listings, LISTING_DAYS, fetch_tickers

FAPI = "https://fapi.binance.com"


def fetch_1m_klines(symbol: str, start_ms: int, end_ms: int) -> list:
    out = []
    cur = start_ms
    while cur < end_ms:
        r = requests.get(
            f"{FAPI}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": "1m",
                "startTime": cur,
                "endTime": end_ms,
                "limit": 1500,
            },
            timeout=20,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        last_open = int(batch[-1][0])
        if last_open <= cur:
            break
        cur = last_open + 1
        time.sleep(0.05)
    return out


def analyze_coin(symbol: str, onboard_ms: int, price_now: float | None) -> dict | None:
    end_24h = onboard_ms + 24 * 3600 * 1000
    end_fetch = max(end_24h, int(time.time() * 1000))
    kl = fetch_1m_klines(symbol, onboard_ms, end_fetch)
    if not kl:
        return None

    listing_price = float(kl[0][1])
    if listing_price <= 0:
        return None

    def max_rise_pct(minutes: int) -> float:
        cutoff = onboard_ms + minutes * 60 * 1000
        highs = [float(k[2]) for k in kl if int(k[0]) < cutoff]
        if not highs:
            highs = [float(kl[0][2])]
        peak = max(highs)
        return round((peak - listing_price) / listing_price * 100, 2)

    max1h = max_rise_pct(60)
    max4h = max_rise_pct(240)

    kl24 = [k for k in kl if int(k[0]) < end_24h] or kl[:240]
    peak_price = max(float(k[2]) for k in kl24)
    peak_ts = next(int(k[0]) for k in kl24 if float(k[2]) == peak_price)

    after = [k for k in kl if int(k[0]) >= peak_ts]
    low_after = min(float(k[3]) for k in after) if after else peak_price
    drop_from_peak = round((peak_price - low_after) / peak_price * 100, 2) if peak_price > 0 else 0.0

    now_pct = None
    if price_now:
        now_pct = round((price_now - listing_price) / listing_price * 100, 2)

    return {
        "listing_price": listing_price,
        "max1h": max1h,
        "max4h": max4h,
        "drop_from_peak": drop_from_peak,
        "now_pct": now_pct,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Listelemeler çekiliyor...", flush=True)
    data = build_recent_listings(days=LISTING_DAYS)
    tickers = fetch_tickers()
    rows = []

    for i, c in enumerate(data["coins"]):
        sym = c["symbol"]
        onboard = c["onboardDateMs"]
        pn = tickers.get(sym)
        print(f"[{i + 1}/{len(data['coins'])}] {c['coin']}...", flush=True)
        try:
            analysis = analyze_coin(sym, onboard, pn)
        except Exception as exc:
            print(f"  HATA: {exc}", flush=True)
            analysis = None
        rows.append({**c, "analysis": analysis})
        time.sleep(0.08)

    print()
    print(f"=== Binance USDT-M Perpetual — Son {data['days']} Gün Listeleme Analizi ===")
    print(f"Toplam: {len(rows)} coin\n")

    hdr = (
        f"{'Coin':<10} {'Listeleme':<16} {'1s Max':>8} {'4s Max':>8} "
        f"{'Zirve↓':>10} {'Şimdi':>10}"
    )
    print(hdr)
    print("-" * len(hdr))

    for r in rows:
        a = r.get("analysis")
        if not a:
            print(f"{r['coin']:<10} {r['listedAt']:<16} {'—':>8} {'—':>8} {'—':>10} {'—':>10}")
            continue
        m1 = f"{a['max1h']:+.1f}%"
        m4 = f"{a['max4h']:+.1f}%"
        drop = f"-{a['drop_from_peak']:.1f}%"
        now = f"{a['now_pct']:+.1f}%" if a["now_pct"] is not None else "—"
        print(f"{r['coin']:<10} {r['listedAt']:<16} {m1:>8} {m4:>8} {drop:>10} {now:>10}")

    valid = [r for r in rows if r.get("analysis")]
    if valid:
        m1s = [r["analysis"]["max1h"] for r in valid]
        m4s = [r["analysis"]["max4h"] for r in valid]
        drops = [r["analysis"]["drop_from_peak"] for r in valid]
        nows = [r["analysis"]["now_pct"] for r in valid if r["analysis"]["now_pct"] is not None]
        print()
        print("=== Özet (ortalama / medyan) ===")
        print(f"1s max yükseliş:      ort {st.mean(m1s):+.1f}%  medyan {st.median(m1s):+.1f}%")
        print(f"4s max yükseliş:      ort {st.mean(m4s):+.1f}%  medyan {st.median(m4s):+.1f}%")
        print(f"Zirve sonrası düşüş:  ort -{st.mean(drops):.1f}%  medyan -{st.median(drops):.1f}%")
        if nows:
            print(f"Şimdi vs listeleme:   ort {st.mean(nows):+.1f}%  medyan {st.median(nows):+.1f}%")


if __name__ == "__main__":
    main()
