#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Son 10 gerçek Merter mesajını parse_merter ile test et."""
from __future__ import annotations

import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from signal_bot.signal_parser import parse_merter

HISTORY = os.path.join(os.path.dirname(__file__), "history", "merter_history.txt")


def _body(line: str) -> str:
    m = re.match(r"\[[^\]]+\] \[MZTR[^\]]+\]\s*(.*)", line)
    return m.group(1) if m else line


def _summary(rec: dict) -> dict:
    return {
        k: rec.get(k)
        for k in (
            "signal_format",
            "symbol",
            "direction",
            "entry_price",
            "stop_price",
            "filter_score",
            "rsi_5m",
        )
        if rec.get(k) is not None
    }


def main() -> None:
    lines = open(HISTORY, encoding="utf-8").read().splitlines()
    last10 = lines[-10:]

    print("=" * 72)
    print("parse_merter — son 10 gerçek mesaj")
    print("=" * 72)

    for i, line in enumerate(last10, 1):
        ts = re.match(r"\[([^\]]+)\]", line)
        ts_str = ts.group(1) if ts else "?"
        body = _body(line)
        records = parse_merter(body)

        print(f"\n--- Mesaj {i} [{ts_str}] ---")
        print(f"Önizleme: {body[:120].replace(chr(10), ' ')}...")
        print(f"Kayıt sayısı: {len(records)}")

        if not records:
            print("  (parse sonucu boş — filtre REJECT veya format eşleşmedi)")
            continue

        for j, rec in enumerate(records, 1):
            print(f"  [{j}] {json.dumps(_summary(rec), ensure_ascii=False)}")
            if rec.get("filter_meta"):
                print(f"       meta: {json.dumps(rec['filter_meta'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
