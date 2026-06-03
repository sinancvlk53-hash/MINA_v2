#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merter 1x DCA pozisyon izleme döngüsü (TP / trailing / 48s)."""
from __future__ import annotations

import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from signal_bot.merter_dca_manager import get_merter_dca_manager

INTERVAL = int(os.environ.get("MERTER_DCA_INTERVAL", "30"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mgr = get_merter_dca_manager()
    print(f"Merter DCA monitor başladı interval={INTERVAL}s", flush=True)
    while True:
        try:
            mgr.monitor_positions()
        except Exception as e:
            print(f"monitor hata: {e}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
