#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance futures yeni listeleme izleyici — 15 dk alarm, 6 saat cache güncelleme."""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from signal_bot.binance_listings import WATCH_INTERVAL_SEC, watcher_cycle


def main() -> None:
    print(f"[BINANCE LISTINGS] Watcher başladı — döngü {WATCH_INTERVAL_SEC // 60} dk")
    while True:
        try:
            watcher_cycle()
        except Exception as exc:
            print(f"[BINANCE LISTINGS] Döngü hatası: {exc}")
        time.sleep(WATCH_INTERVAL_SEC)


if __name__ == "__main__":
    main()
