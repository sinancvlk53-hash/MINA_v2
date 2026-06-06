#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Haluk upbit/listing mesajları — coin bazlı Binance fiyat analizi → listing_analysis.md"""
from __future__ import annotations

import os
import sys
import time
import statistics as st
from datetime import datetime, timezone, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from signal_bot.haluk_message_store import query_upbit_listings, _ts_to_ms

FAPI = "https://fapi.binance.com"
OUT_PATH = os.path.join(ROOT, "signal_bot", "history", "listing_analysis.md")
TR = timezone(timedelta(hours=3))


def fetch_exchange_symbols() -> set[str]:
    r = requests.get(f"{FAPI}/fapi/v1/exchangeInfo", timeout=30)
    r.raise_for_status()
    return {
        s["symbol"]
        for s in r.json().get("symbols", [])
        if str(s.get("symbol", "")).endswith("USDT")
        and s.get("status") == "TRADING"
        and s.get("contractType") == "PERPETUAL"
    }


def fetch_price_now() -> dict[str, float]:
    r = requests.get(f"{FAPI}/fapi/v1/ticker/price", timeout=30)
    r.raise_for_status()
    return {row["symbol"]: float(row["price"]) for row in r.json()}


def fetch_klines(symbol: str, start_ms: int, interval: str = "1h") -> list:
    out = []
    cur = start_ms
    end_ms = int(time.time() * 1000)
    while cur < end_ms:
        r = requests.get(
            f"{FAPI}/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": cur,
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
        time.sleep(0.04)
    return out


def fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=TR).strftime("%Y-%m-%d %H:%M")


def analyze_coin(symbol: str, mention_ms: int, price_now: float | None) -> dict | None:
    kl = fetch_klines(symbol, mention_ms, "1h")
    if not kl:
        return None

    price_then = float(kl[0][4])
    if price_then <= 0:
        return None

    peak_price = price_then
    peak_ts = int(kl[0][0])
    for k in kl:
        high = float(k[2])
        if high > peak_price:
            peak_price = high
            peak_ts = int(k[0])

    after = [k for k in kl if int(k[0]) >= peak_ts]
    low_after = min(float(k[3]) for k in after) if after else peak_price

    max_rise_pct = round((peak_price - price_then) / price_then * 100, 2)
    drop_from_peak = round((peak_price - low_after) / peak_price * 100, 2) if peak_price > 0 else 0.0
    now_pct = None
    if price_now:
        now_pct = round((price_now - price_then) / price_then * 100, 2)

    return {
        "price_then": price_then,
        "peak_price": peak_price,
        "peak_at": fmt_ts(peak_ts),
        "max_rise_pct": max_rise_pct,
        "drop_from_peak": drop_from_peak,
        "now_pct": now_pct,
        "price_now": price_now,
    }


def build_markdown(rows: list[dict], meta: dict) -> str:
    lines = [
        "# Haluk Upbit / Listeleme Coin Analizi",
        "",
        f"**Oluşturulma:** {meta['generated_at']} TR",
        f"**Kaynak:** `haluk_messages` (upbit / listing / listeleme)",
        f"**Mesaj sayısı:** {meta['total_messages']}",
        f"**Coin sayısı:** {meta['total_coins']}",
        "",
        "## Metodoloji",
        "",
        "| Metrik | Açıklama |",
        "|--------|----------|",
        "| **İlk bahis fiyatı** | Hoca'nın ilk bahsettiği tarihteki saatlik kapanış (Binance Futures) |",
        "| **Max yükseliş** | İlk bahisten sonraki en yüksek high ve tarihi |",
        "| **Zirve↓** | Zirve anından bugüne görülen en düşük low → zirveye göre düşüş % |",
        "| **Şimdi** | Güncel fiyat vs ilk bahis fiyatı |",
        "",
        "## Coin Tablosu",
        "",
        "| Coin | İlk Bahis | İlk Fiyat | Max ↑ | Zirve Tarihi | Zirve↓ | Şimdi | Bahis # |",
        "|------|-----------|-----------|-------|--------------|--------|-------|---------|",
    ]

    for r in rows:
        a = r.get("analysis")
        if not a:
            lines.append(
                f"| {r['coin']} | {r['firstMention'][:16]} | — | — | — | — | — | {r['mentionCount']} |"
            )
            continue
        pt = f"{a['price_then']:.6g}"
        max_up = f"+{a['max_rise_pct']:.1f}%"
        drop = f"-{a['drop_from_peak']:.1f}%"
        now = f"{a['now_pct']:+.1f}%" if a["now_pct"] is not None else "—"
        lines.append(
            f"| **{r['coin']}** | {r['firstMention'][:16]} | {pt} | {max_up} | {a['peak_at']} | {drop} | {now} | {r['mentionCount']} |"
        )

    valid = [r for r in rows if r.get("analysis")]
    if valid:
        rises = [r["analysis"]["max_rise_pct"] for r in valid]
        drops = [r["analysis"]["drop_from_peak"] for r in valid]
        nows = [r["analysis"]["now_pct"] for r in valid if r["analysis"]["now_pct"] is not None]
        lines.extend([
            "",
            "## Özet",
            "",
            f"- Max yükseliş ortalama: **+{st.mean(rises):.1f}%** (medyan +{st.median(rises):.1f}%)",
            f"- Zirve sonrası düşüş ortalama: **-{st.mean(drops):.1f}%** (medyan -{st.median(drops):.1f}%)",
        ])
        if nows:
            lines.append(
                f"- Şimdi vs ilk bahis ortalama: **{st.mean(nows):+.1f}%** (medyan {st.median(nows):+.1f}%)"
            )

    lines.append("")
    return "\n".join(lines)


def main():
    data = query_upbit_listings(limit=500, client=None)
    valid_syms = fetch_exchange_symbols()
    prices = fetch_price_now()

    rows = []
    coins = data.get("coins") or []
    print(f"Toplam {len(coins)} coin, analiz başlıyor...", flush=True)

    for i, c in enumerate(coins):
        coin = c["coin"]
        sym = f"{coin}USDT"
        mention_ms = _ts_to_ms(c.get("firstMention") or "")
        print(f"[{i + 1}/{len(coins)}] {coin}...", flush=True)

        row = {**c, "analysis": None, "on_binance": sym in valid_syms}
        if sym not in valid_syms or not mention_ms:
            rows.append(row)
            continue

        try:
            row["analysis"] = analyze_coin(sym, mention_ms, prices.get(sym))
        except Exception as exc:
            print(f"  HATA {coin}: {exc}", flush=True)
        rows.append(row)
        time.sleep(0.08)

    meta = {
        "generated_at": datetime.now(tz=TR).strftime("%Y-%m-%d %H:%M"),
        "total_messages": data.get("total", 0),
        "total_coins": len(coins),
    }
    md = build_markdown(rows, meta)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\nYazıldı: {OUT_PATH}")
    print(md[:2000])


if __name__ == "__main__":
    main()
