#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merter DCA filtre testi — RVOL + RSI teyit (canlı Binance, emir yok)."""
from __future__ import annotations

import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from signal_bot.merter_dca_manager import MerterDCAManager, RVOL_MIN

HISTORY = os.path.join(_ROOT, "signal_bot", "history", "merter_history.txt")


def _body(line: str) -> str:
    m = re.match(r"\[[^\]]+\] \[MZTR[^\]]+\]\s*(.*)", line)
    return m.group(1) if m else line


def main() -> None:
    mgr = MerterDCAManager()
    budget = mgr.slot_budget()
    part = mgr.part_usdt()
    print("=" * 60)
    print("MERTER 1x DCA — filtre testi")
    print("=" * 60)
    print(f"slot_budget (balance/10): {budget:.4f} USDT")
    print(f"part_usdt (slot/10):      {part:.4f} USDT")
    print(f"RVOL eşiği:              >={RVOL_MIN}")
    print()

    lines = open(HISTORY, encoding="utf-8").read().splitlines()
    last10 = lines[-10:]

    for i, line in enumerate(last10, 1):
        body = _body(line)
        ts = re.match(r"\[([^\]]+)\]", line)
        print(f"\n--- Mesaj {i} [{ts.group(1) if ts else '?'}] ---")
        print(body[:100].replace("\n", " ") + "...")

        if "Sinyal Taraması" in body or "Yeni AL Sinyalleri" in body:
            syms = mgr._extract_ei_long_symbols(body)
            print(f"  EI AL coin sayısı: {len(syms)}")
            ranked = []
            for sym in syms[:8]:
                rvol = mgr.calculate_rvol(sym)
                ok = rvol is not None and rvol >= RVOL_MIN
                rvol_s = f"{rvol:.2f}" if rvol is not None else "N/A"
                print(f"    {sym} RVOL={rvol_s}{' OK' if ok else ' REJECT'}")
                if ok:
                    ranked.append((sym, rvol))
            if ranked:
                ranked.sort(key=lambda x: -x[1])
                print(f"  → SEÇİLİR: {ranked[0][0]} RVOL={ranked[0][1]:.2f}")
            else:
                print("  → REJECT: RVOL>=2.0 yok")
            continue

        if "RSI Analizi" in body:
            sym = mgr.check_rsi_signal(body)
            if sym:
                print(f"  → RSI TEYİT OK: {sym}")
            else:
                print("  → RSI REJECT")
            continue

        print("  (legacy/sohbet — DCA dışı)")

    print("\n" + "=" * 60)
    print("Test tamam — canlı emir gönderilmedi.")


if __name__ == "__main__":
    main()
