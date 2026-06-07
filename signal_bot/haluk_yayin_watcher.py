#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Haluk yayın özeti hatırlatıcı döngüsü — haluk_predictions hedef tarih."""
from __future__ import annotations

import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from signal_bot.haluk_predictions import init_predictions_table, send_prediction_reminders

CHECK_SEC = int(os.environ.get("HALUK_PRED_CHECK_SEC", "3600"))


def main() -> None:
    init_predictions_table()
    print(f"[HALUK YAYIN WATCHER] başladı check={CHECK_SEC}s", flush=True)
    while True:
        try:
            n = send_prediction_reminders()
            if n:
                print(f"[HALUK YAYIN WATCHER] {n} hatırlatma gönderildi", flush=True)
        except Exception as exc:
            print(f"[HALUK YAYIN WATCHER] hata: {exc}", flush=True)
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    main()
