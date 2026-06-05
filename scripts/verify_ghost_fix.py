#!/usr/bin/env python3
"""Hayalet düzeltmesi doğrulama — MOVR hayalet olmamalı."""
import os
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

from ghost_positions import merter_dca_tracked_keys, detect_ghost_positions, is_merter_dca_position
from backend.config import BinanceConfig

keys = merter_dca_tracked_keys()
print("Merter DCA tracked keys:", sorted(keys))
print("MOVR is merter:", is_merter_dca_position("MOVRUSDT", "LONG", 1))

client = BinanceConfig().get_client()
raw = client.futures_position_information()
ghosts = detect_ghost_positions(raw)
movr_ghosts = [g for g in ghosts if g["symbol"] == "MOVRUSDT"]
print("MOVR ghosts:", movr_ghosts if movr_ghosts else "NONE (OK)")
print("Total ghosts:", len(ghosts), [f"{g['symbol']}/{g['side']}" for g in ghosts])
