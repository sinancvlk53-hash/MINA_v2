#!/usr/bin/env python3
"""ht_pdf_basari_orani — fiyat takip kolonları migrasyonu."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from signal_bot.ht_pdf_price_monitor import init_ht_pdf_price_columns

if __name__ == "__main__":
    init_ht_pdf_price_columns()
    print("ht_pdf_basari_orani fiyat kolonları hazır")
