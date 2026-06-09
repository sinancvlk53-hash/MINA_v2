#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINA Makro İzleyici — 15 dk döngü, piyasa rejimi + Telegram."""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from mina_makro_core import WATCH_INTERVAL_SEC, watcher_cycle


def main() -> None:
    print(f"[MAKRO WATCHER] Başladı — döngü {WATCH_INTERVAL_SEC // 60} dk")
    while True:
        try:
            watcher_cycle()
        except Exception as exc:
            print(f"[MAKRO WATCHER] Döngü hatası: {exc}")
        time.sleep(WATCH_INTERVAL_SEC)


if __name__ == "__main__":
    main()
