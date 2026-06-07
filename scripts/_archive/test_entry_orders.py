#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resolve_entry_order — limit vs market seçimi testi (unit + canlı mark)."""
from __future__ import annotations

import datetime
from datetime import timezone
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET

from mina_entry_orders import resolve_entry_order

LOG_PATH = os.path.join(ROOT, "mina_bot.log")


def _log(line: str) -> None:
    ts = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[ENTRY_TEST] {line}"
    print(msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except OSError:
        pass


def run_unit_tests() -> bool:
    cases = [
        ("LONG", 95.0, 100.0, ORDER_TYPE_LIMIT, 95.0),
        ("LONG", 105.0, 100.0, ORDER_TYPE_MARKET, None),
        ("SHORT", 105.0, 100.0, ORDER_TYPE_LIMIT, 105.0),
        ("SHORT", 95.0, 100.0, ORDER_TYPE_MARKET, None),
        ("LONG", None, 100.0, ORDER_TYPE_MARKET, None),
    ]
    ok = True
    for side, entry, mark, expected_type, expected_px in cases:
        order_type, limit_px = resolve_entry_order(side, entry, mark)
        passed = order_type == expected_type and limit_px == expected_px
        ok = ok and passed
        _log(
            f"unit {side} entry={entry} mark={mark} -> type={order_type} px={limit_px} "
            f"expected={expected_type}/{expected_px} {'PASS' if passed else 'FAIL'}"
        )
    return ok


def run_live_sample() -> None:
    try:
        from config import BinanceConfig

        client = BinanceConfig().get_client()
        sym = "BTCUSDT"
        mark = float(client.futures_mark_price(symbol=sym)["markPrice"])
        below = round(mark * 0.99, 2)
        above = round(mark * 1.01, 2)
        for label, entry in (("altinda", below), ("ustunde", above)):
            order_type, limit_px = resolve_entry_order("LONG", entry, mark)
            action = "LIMIT borsaya gonder" if order_type == ORDER_TYPE_LIMIT else "MARKET kullan"
            _log(f"live {sym} mark={mark:.2f} entry={entry:.2f} ({label}) -> {action} px={limit_px}")
    except Exception as exc:
        _log(f"live skip: {exc}")


def main() -> None:
    unit_ok = run_unit_tests()
    run_live_sample()
    _log(f"sonuc={'TUM TESTLER GECTI' if unit_ok else 'BASARISIZ TEST VAR'}")
    sys.exit(0 if unit_ok else 1)


if __name__ == "__main__":
    main()
