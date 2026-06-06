#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upbit listeleme habercisi — 30 sn döngü."""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from signal_bot.upbit_listing_reporter import WATCH_INTERVAL_SEC, watcher_cycle


def main() -> None:
    print(f"[UPBIT LISTING] Watcher başladı — döngü {WATCH_INTERVAL_SEC} sn")
    while True:
        try:
            n, sent = watcher_cycle()
            if n:
                print(f"[UPBIT LISTING] Döngü: {n} alarm, {sent} Telegram")
        except Exception as exc:
            print(f"[UPBIT LISTING] Döngü hatası: {exc}")
        time.sleep(WATCH_INTERVAL_SEC)


if __name__ == "__main__":
    main()
