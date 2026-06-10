#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gece orphan emir temizliği — Merter state vs Binance + stale Haluk PDF limitler."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

LOG_FILE = os.path.join(_ROOT, "signal_bot", "orphan_cleaner.log")


def _log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    from binance.client import Client
    from mina_orphan_orders import run_full_orphan_cleanup

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        _log("[ORPHAN] HATA: BINANCE_API_KEY/SECRET yok")
        return 1

    testnet = os.getenv("BINANCE_TESTNET", "true").strip().lower() in ("1", "true", "yes")
    client = Client(api_key, api_secret, testnet=testnet)

    _log("[ORPHAN] Temizlik başladı")
    try:
        summary = run_full_orphan_cleanup(client, log=_log)
        _log(f"[ORPHAN] Tamamlandı: {summary}")
        return 0
    except Exception as exc:
        _log(f"[ORPHAN] FATAL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
