#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kapalı coinlerin tracking JSON kayıtlarını sil."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import mina_tracking as mt

SYMBOLS = ("SOLUSDT", "INJUSDT", "LINKUSDT")
SIDES = ("LONG", "SHORT")


def scrub_dict(data: dict, symbols: tuple[str, ...]) -> int:
    remove_keys: set[str] = set()
    for sym in symbols:
        remove_keys.add(sym)
        for side in SIDES:
            remove_keys.add(mt.pos_key(sym, side))
    n = 0
    for k in list(data.keys()):
        if k in remove_keys:
            data.pop(k, None)
            n += 1
    return n


def main() -> None:
    print("=== Tracking temizliği:", ", ".join(SYMBOLS), "===")

    total = 0
    for fn in mt.TRACKING_FILES:
        data = mt.load_json(fn)
        scrubbed = scrub_dict(data, SYMBOLS)
        if scrubbed:
            mt.save_json(fn, data)
            print(f"OK  {fn}: {scrubbed} anahtar silindi")
            total += scrubbed
        else:
            print(f"—   {fn}: temiz")

    state_path = os.path.join(ROOT, "mina_position_state.json")
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            for sym in SYMBOLS:
                if sym in state:
                    state.pop(sym, None)
                    total += 1
                    print(f"OK  mina_position_state.json: {sym} silindi")
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                f.write("\n")

    print(f"\nToplam silinen: {total}")


if __name__ == "__main__":
    main()
