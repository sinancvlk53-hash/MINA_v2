#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bugünkü Haluk Telegram mesajları — pozisyon / bekleyen pomuz taraması."""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
TODAY = os.environ.get("SCAN_DATE", "2026-06-04")

sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIG = os.path.join(ROOT, "signal_bot", "signals_log.txt")
QUEUE = os.path.join(ROOT, "signal_bot", "raw_signal_queue.json")

POS_KW = re.compile(
    r"bekleyen\s+pomuz|pomuz|pozisyon|poz\b|karda|kar\s*al|stop\s*at|tp['']?yi|girişe\s*stop",
    re.I,
)


def main() -> None:
    print("=" * 72)
    print(f"HALUK signals_log — {TODAY}")
    print("=" * 72)
    haluk_lines = []
    if os.path.isfile(SIG):
        for line in open(SIG, encoding="utf-8", errors="replace"):
            if TODAY not in line or "[HALUK]" not in line:
                continue
            haluk_lines.append(line.rstrip())
            print(line.rstrip()[:600])

    print(f"\nToplam Haluk satır: {len(haluk_lines)}")

    print("\n" + "=" * 72)
    print("Pozisyon / bekleyen pomuz içeren mesajlar")
    print("=" * 72)
    hits = [l for l in haluk_lines if POS_KW.search(l)]
    if not hits:
        print("(eşleşme yok)")
    for l in hits:
        print(l[:600])

    print("\n" + "=" * 72)
    print(f"raw_signal_queue — haluk telegram {TODAY}")
    print("=" * 72)
    if not os.path.isfile(QUEUE):
        print("(kuyruk yok)")
        return

    q = json.load(open(QUEUE, encoding="utf-8"))
    entries = q.get("entries") or []
    haluk_today = [
        e for e in entries
        if "haluk" in str(e.get("source", "")).lower()
        and TODAY in str(e.get("timestamp", ""))
    ]
    print(f"Bugün haluk kayıt: {len(haluk_today)}")
    for e in haluk_today:
        raw = (e.get("raw_snippet") or e.get("raw_text") or "")[:200]
        print(json.dumps({
            "timestamp": e.get("timestamp"),
            "source": e.get("source"),
            "symbol": e.get("symbol"),
            "status": e.get("status"),
            "reject_reason": e.get("reject_reason"),
            "direction": e.get("direction"),
            "entry_price": e.get("entry_price"),
            "snippet": raw,
        }, ensure_ascii=False))
        if POS_KW.search(raw):
            approved = e.get("status") == "approved"
            print(f"  → pozisyon mesajı | approved={approved} | emir={'EVET (K2)' if approved else 'HAYIR'}")

    print("\n" + "=" * 72)
    print("Parser test — BCH örnek mesaj")
    print("=" * 72)
    from signal_bot.signal_parser import extract_haluk_symbol, parse_haluk_telegram

    sample = (
        "Dostlar bunda plan değişikliğine gidiyoruz.\n"
        "BCH şu an %6.43 karda, önce yarım kar alın ve girişe stop atın burdan."
    )
    print("extract_haluk_symbol:", extract_haluk_symbol(sample))
    recs, pause = parse_haluk_telegram(sample)
    print("parse:", json.dumps(recs, ensure_ascii=False, indent=2))
    print("pause:", pause)


if __name__ == "__main__":
    main()
