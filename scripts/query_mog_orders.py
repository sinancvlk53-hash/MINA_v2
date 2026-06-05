#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1000000MOGUSDT emir geçmişi + merter_dca_state MOG kaydı."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from config import BinanceConfig

SYMBOL = "1000000MOGUSDT"
TODAY = "2026-06-04"


def main() -> None:
    client = BinanceConfig().get_client()

    print("=" * 72)
    print(f"Binance futures_get_all_orders — {SYMBOL} (son 5)")
    print("=" * 72)
    try:
        orders = client.futures_get_all_orders(symbol=SYMBOL, limit=500)
    except Exception as e:
        print(f"HATA: {e}")
        orders = []

    # Bugün 19:30 UTC civarı (log: 2026-06-04T19:30:21Z)
    window_start = datetime(2026, 6, 4, 19, 25, 0, tzinfo=timezone.utc).timestamp() * 1000
    window_end = datetime(2026, 6, 4, 19, 40, 0, tzinfo=timezone.utc).timestamp() * 1000

    today_orders = []
    window_orders = []
    for o in orders:
        ts = int(o.get("time") or o.get("updateTime") or 0)
        tstr = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if tstr.startswith(TODAY):
            today_orders.append((ts, tstr, o))
        if window_start <= ts <= window_end:
            window_orders.append((ts, tstr, o))

    print(f"Toplam dönen emir: {len(orders)} | bugün ({TODAY}): {len(today_orders)}")
    print(f"19:25–19:40 UTC penceresi: {len(window_orders)} emir\n")

    if window_orders:
        print("--- 19:30 civarı emirler ---")
        for ts, tstr, o in sorted(window_orders, key=lambda x: x[0]):
            print(
                f"{tstr} | {o.get('type'):<12} {o.get('side'):<5} "
                f"qty={o.get('origQty')} price={o.get('price')} "
                f"status={o.get('status')} orderId={o.get('orderId')} "
                f"avgPrice={o.get('avgPrice', '—')}"
            )
    else:
        print("(19:30 UTC penceresinde emir yok)")

    print("\n--- Son 5 emir (tüm zamanlar) ---")
    sorted_orders = sorted(orders, key=lambda x: int(x.get("updateTime") or x.get("time") or 0), reverse=True)
    for o in sorted_orders[:5]:
        ts = int(o.get("updateTime") or o.get("time") or 0)
        tstr = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(
            f"{tstr} | {o.get('type'):<12} {o.get('side'):<5} "
            f"qty={o.get('origQty')} price={o.get('price')} "
            f"status={o.get('status')} orderId={o.get('orderId')} "
            f"avgPrice={o.get('avgPrice', '—')}"
        )

    print("\n" + "=" * 72)
    print("merter_dca_state.json — MOG kaydı")
    print("=" * 72)
    state_path = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    mog_found = []
    for yuva, pos in (state.get("positions") or {}).items():
        if not pos:
            continue
        sym = str(pos.get("symbol", ""))
        if "MOG" in sym.upper():
            mog_found.append((yuva, pos))

    if mog_found:
        for yuva, pos in mog_found:
            print(f"\nYuva: {yuva}")
            print(json.dumps(pos, indent=2, ensure_ascii=False))
    else:
        print("MOG kaydı YOK — state içeriği:")
        print(json.dumps(state, indent=2, ensure_ascii=False))

    print("\n" + "=" * 72)
    print("Açık pozisyon (Binance)")
    print("=" * 72)
    for p in client.futures_position_information(symbol=SYMBOL):
        amt = float(p.get("positionAmt") or 0)
        if amt != 0:
            print(f"  {p.get('positionSide')} amt={amt} entry={p.get('entryPrice')} margin={p.get('isolatedMargin')}")
    else:
        print("  (açık pozisyon yok)")


if __name__ == "__main__":
    main()
