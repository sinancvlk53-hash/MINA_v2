#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Son 90 günde Upbit KRW'de listelenen ve Binance Futures'ta da işlem gören coinler.
Upbit listeleme tarihi (ilk günlük mum), Binance onboardDate, fark, listeleme günü Binance max ↑↓.
"""
from __future__ import annotations

import os
import sys
import time
import statistics as st
from datetime import datetime, timezone, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAPI = "https://fapi.binance.com"
UPBIT = "https://api.upbit.com/v1"
DAYS = 90
KST = timezone(timedelta(hours=9))


def upbit_get(path: str, params: dict | None = None) -> list | dict:
    for attempt in range(3):
        try:
            r = requests.get(f"{UPBIT}{path}", params=params or {}, timeout=20)
            if r.status_code == 429:
                time.sleep(1.5)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.5)
    return []


def binance_get(path: str, params: dict | None = None) -> list | dict:
    r = requests.get(f"{FAPI}{path}", params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_upbit_krw_markets() -> list[str]:
    data = upbit_get("/market/all")
    return sorted(
        m["market"]
        for m in data
        if str(m.get("market", "")).startswith("KRW-")
    )


def upbit_listing_date_kst(market: str, cutoff_ms: int) -> int | None:
    """Son 90 gün içinde listelendiyse ilk günlük mum timestamp (ms, UTC), değilse None."""
    candles = upbit_get("/candles/days", {"market": market, "count": DAYS + 1})
    if not candles:
        return None
    oldest = candles[-1]
    ts_str = oldest.get("candle_date_time_utc") or oldest.get("candle_date_time_kst")
    if not ts_str:
        return None
    ts_str = ts_str.replace("T", " ").replace("Z", "")[:19]
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    ts_ms = int(dt.timestamp() * 1000)
    if len(candles) >= DAYS + 1:
        return None
    if ts_ms < cutoff_ms:
        return None
    return ts_ms


def fetch_binance_perp_map() -> dict[str, int]:
    info = binance_get("/fapi/v1/exchangeInfo")
    out: dict[str, int] = {}
    for s in info.get("symbols", []):
        sym = str(s.get("symbol") or "")
        if not sym.endswith("USDT"):
            continue
        if s.get("contractType") != "PERPETUAL":
            continue
        if s.get("status") != "TRADING":
            continue
        out[sym] = int(s.get("onboardDate") or 0)
    return out


def fmt_dt(ms: int, tz=KST) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=tz).strftime("%Y-%m-%d %H:%M")


def fmt_delta(upbit_ms: int, binance_ms: int) -> str:
    diff_h = (upbit_ms - binance_ms) / 3600000
    if abs(diff_h) < 24:
        return f"{diff_h:+.1f} saat"
    diff_d = diff_h / 24
    return f"{diff_d:+.1f} gün"


def kst_day_bounds_ms(upbit_ms: int) -> tuple[int, int]:
    dt = datetime.fromtimestamp(upbit_ms / 1000, tz=KST)
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return int(day_start.timestamp() * 1000), int(day_end.timestamp() * 1000)


def binance_listing_day_stats(symbol: str, upbit_ms: int) -> dict | None:
    start_ms, end_ms = kst_day_bounds_ms(upbit_ms)
    kl = binance_get("/fapi/v1/klines", {
        "symbol": symbol,
        "interval": "1h",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 48,
    })
    if not kl:
        return None

    ref_idx = 0
    for i, k in enumerate(kl):
        if int(k[0]) >= upbit_ms:
            ref_idx = max(i - 1, 0)
            break
    ref_price = float(kl[ref_idx][4])
    if ref_price <= 0:
        ref_price = float(kl[ref_idx][1])

    peak = ref_price
    trough = ref_price
    for k in kl[ref_idx:]:
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        # Fitil glitch: high > 3× body üst sınırı → close/open ile sınırla
        body_top = max(o, c)
        eff_h = h if h <= body_top * 3 else body_top
        eff_l = l if l >= min(o, c) / 3 else min(o, c)
        peak = max(peak, eff_h)
        trough = min(trough, eff_l)

    max_up = round((peak - ref_price) / ref_price * 100, 2)
    max_down = round((ref_price - trough) / ref_price * 100, 2)
    return {"max_up": max_up, "max_down": max_down, "ref_price": ref_price}


def main():
    cutoff_ms = int((time.time() - DAYS * 86400) * 1000)
    print(f"Upbit KRW marketler taranıyor (son {DAYS} gün)...", flush=True)

    markets = fetch_upbit_krw_markets()
    binance_map = fetch_binance_perp_map()
    print(f"Upbit KRW: {len(markets)}, Binance Perp: {len(binance_map)}", flush=True)

    candidates: list[dict] = []
    for i, market in enumerate(markets):
        coin = market.replace("KRW-", "")
        sym = f"{coin}USDT"
        if sym not in binance_map:
            continue
        if (i + 1) % 50 == 0:
            print(f"  Upbit tarama {i + 1}/{len(markets)}...", flush=True)
        try:
            upbit_ms = upbit_listing_date_kst(market, cutoff_ms)
        except Exception:
            continue
        if not upbit_ms:
            continue
        binance_ms = binance_map[sym]
        candidates.append({
            "coin": coin,
            "symbol": sym,
            "market": market,
            "upbit_ms": upbit_ms,
            "binance_ms": binance_ms,
        })
        time.sleep(0.12)

    candidates.sort(key=lambda x: x["upbit_ms"], reverse=True)
    print(f"\nEşleşen (son {DAYS} gün Upbit + Binance Futures): {len(candidates)} coin\n", flush=True)

    rows = []
    for i, c in enumerate(candidates):
        print(f"[{i + 1}/{len(candidates)}] {c['coin']} Binance gün analizi...", flush=True)
        try:
            stats = binance_listing_day_stats(c["symbol"], c["upbit_ms"])
        except Exception as exc:
            print(f"  HATA: {exc}", flush=True)
            stats = None
        rows.append({**c, "stats": stats})
        time.sleep(0.08)

    now_str = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Upbit ↔ Binance Futures Listeleme Çapraz Analizi (Son {DAYS} Gün)",
        "",
        f"**Oluşturulma:** {now_str} KST",
        f"**Upbit listeleme tarihi:** İlk günlük mum (KRW piyasası)",
        f"**Binance tarihi:** `onboardDate` (Futures perpetual)",
        f"**Fark:** Upbit − Binance (pozitif = Upbit daha geç)",
        f"**Listeleme günü Binance:** Upbit listeleme anından o gün sonuna (KST) max yükseliş / düşüş",
        "",
        f"**Toplam eşleşme:** {len(rows)} coin",
        "",
        "| Coin | Upbit Listeleme | Binance Başlangıç | Fark | Gün Max ↑ | Gün Max ↓ |",
        "|------|-----------------|-------------------|------|-----------|-----------|",
    ]

    for r in rows:
        up = fmt_dt(r["upbit_ms"])
        bn = fmt_dt(r["binance_ms"])
        diff = fmt_delta(r["upbit_ms"], r["binance_ms"])
        stt = r.get("stats")
        if stt:
            mu = f"+{stt['max_up']:.1f}%"
            md = f"-{stt['max_down']:.1f}%"
        else:
            mu = md = "—"
        lines.append(f"| **{r['coin']}** | {up} | {bn} | {diff} | {mu} | {md} |")

    valid = [r for r in rows if r.get("stats")]
    if valid:
        ups = [r["stats"]["max_up"] for r in valid]
        downs = [r["stats"]["max_down"] for r in valid]
        diffs_h = [(r["upbit_ms"] - r["binance_ms"]) / 3600000 for r in valid]
        lines.extend([
            "",
            "## Özet",
            "",
            f"- Upbit listeleme günü Binance max yükseliş: ort **+{st.mean(ups):.1f}%**, medyan **+{st.median(ups):.1f}%**",
            f"- Upbit listeleme günü Binance max düşüş: ort **-{st.mean(downs):.1f}%**, medyan **-{st.median(downs):.1f}%**",
            f"- Upbit vs Binance zaman farkı: ort **{st.mean(diffs_h) / 24:+.1f} gün**, medyan **{st.median(diffs_h) / 24:+.1f} gün**",
        ])

    md = "\n".join(lines) + "\n"
    out = os.path.join(ROOT, "signal_bot", "history", "upbit_binance_cross_analysis.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)

    print(md)
    print(f"Yazıldı: {out}")


if __name__ == "__main__":
    main()
