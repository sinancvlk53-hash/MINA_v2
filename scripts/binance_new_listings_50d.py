#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI — son N günde Binance mainnet perpetual listelemeleri."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from signal_bot.binance_listings import build_recent_listings, LISTING_DAYS


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = build_recent_listings(days=LISTING_DAYS)
    print(f"=== Binance USDT-M — son {data['days']} gün ({data['total']} sembol) ===\n")
    print(f"{'Coin':<12} {'Listeleme':<18} {'İlk':>10} {'Güncel':>10} {'Δ':>8}")
    print("-" * 65)
    for row in data["coins"]:
        then_s = f"{row['priceThen']:.6g}" if row.get("priceThen") else "—"
        now_s = f"{row['priceNow']:.6g}" if row.get("priceNow") else "—"
        pct = row.get("priceChangePct")
        pct_s = f"{pct:+.1f}%" if pct is not None else "—"
        print(f"{row['coin']:<12} {row['listedAt']:<18} {then_s:>10} {now_s:>10} {pct_s:>8}")


if __name__ == "__main__":
    main()
