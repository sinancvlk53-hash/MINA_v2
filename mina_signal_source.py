# -*- coding: utf-8 -*-
"""Pozisyon açılış kaynağı kodları (HT / MZ / MANUEL)."""

from __future__ import annotations

from typing import Optional

import mina_tracking as mt

HT = "HT"
MZ = "MZ"
MANUEL = "MANUEL"

SOURCE_LABELS = {
    HT: "Haluk Hoca",
    MZ: "Merter",
    MANUEL: "Manuel",
}


def format_open_log(source: str, symbol: str, side: str) -> str:
    """Örn: HT: BTCUSDT LONG açıldı"""
    code = normalize_source_code(source)
    return f"{code}: {symbol} {side} açıldı"


def normalize_source_code(source: Optional[str]) -> str:
    if not source:
        return HT
    s = str(source).upper()
    if s in (HT, MZ, MANUEL):
        return s
    if s in ("HALUK", "HALUK_PDF", "HALUK_TELEGRAM", "HT"):
        return HT
    if s in ("MERTER", "MERter_EI", "MERter_EI_1", "MERter_EI_2", "MERter_OTHER"):
        return MZ
    if s.startswith("MERter"):
        return MZ
    if s in ("MANUAL", "MANUEL", "MANUAL_OPEN"):
        return MANUEL
    return HT


def queue_source_to_code(queue_source: Optional[str]) -> str:
    """raw_signal_queue entry source → HT/MZ."""
    if not queue_source:
        return HT
    s = str(queue_source).lower()
    if s == "merter":
        return MZ
    if s in ("haluk_pdf", "haluk_telegram", "haluk", "ht"):
        return HT
    return HT


def record_position_source(symbol: str, side: str, source: str) -> None:
    code = normalize_source_code(source)
    key = mt.pos_key(symbol, side)
    data = mt.load_json(mt.POSITION_SOURCE_FILE)
    data[key] = code
    mt.save_json(mt.POSITION_SOURCE_FILE, data)


def clear_position_source(symbol: str, side: str) -> None:
    key = mt.pos_key(symbol, side)
    data = mt.load_json(mt.POSITION_SOURCE_FILE)
    if key in data:
        data.pop(key, None)
        mt.save_json(mt.POSITION_SOURCE_FILE, data)


def get_position_sources() -> dict:
    return mt.load_json(mt.POSITION_SOURCE_FILE)
