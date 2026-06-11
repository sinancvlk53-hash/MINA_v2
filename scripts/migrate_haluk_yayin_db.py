#!/usr/bin/env python3
"""Sunucuda haluk_yayin_summaries + haluk_coin_analizleri şema migrasyonu."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from signal_bot.haluk_yayin_db import init_yayin_tables

if __name__ == "__main__":
    init_yayin_tables()
    print("haluk_yayin DB şeması hazır")
