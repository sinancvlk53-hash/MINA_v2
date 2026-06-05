# -*- coding: utf-8 -*-
"""Pozisyon açılış kaynağı kodları (HT / MZ / MANUEL)."""

from __future__ import annotations

import os
from typing import Optional

import mina_tracking as mt

_ROOT = os.path.dirname(os.path.abspath(__file__))

HT = "HT"
MZ = "MZ"
MANUEL = "MANUEL"
YETIM = "yetim"

SOURCE_LABELS = {
    HT: "Haluk Hoca",
    MZ: "Merter",
    MANUEL: "Manuel",
    YETIM: "Yetim",
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
    if s in ("YETIM", "ORPHAN"):
        return YETIM
    if s.startswith("MERTER"):
        return MZ
    return HT


def detect_orphan_signal_source(symbol: str, side: str) -> str:
    """Yetim pozisyon kaynağı: Merter izi varsa MZ, yoksa yetim."""
    key = mt.pos_key(symbol, side)
    ps = get_position_sources()
    if key in ps:
        return ps[key]

    state_path = os.path.join(_ROOT, "signal_bot", "merter_dca_state.json")
    try:
        state = mt.load_json(state_path) if os.path.isfile(state_path) else {}
        for pos in (state.get("positions") or {}).values():
            if pos and pos.get("symbol") == symbol:
                return MZ
    except Exception:
        pass

    merter_log = os.path.join(_ROOT, "signal_bot", "merter_dca.log")
    try:
        if os.path.isfile(merter_log):
            sym_u = symbol.upper()
            with open(merter_log, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if sym_u not in line.upper():
                        continue
                    if "AÇILDI" in line or "MARKET" in line:
                        return MZ
    except Exception:
        pass

    db = os.path.join(_ROOT, "mina_trading_journal.db")
    try:
        if os.path.isfile(db):
            import sqlite3
            con = sqlite3.connect(db)
            row = con.execute(
                """SELECT signal_source FROM trades
                   WHERE symbol=? AND side=? AND signal_source LIKE 'merter%'
                   ORDER BY id DESC LIMIT 1""",
                (symbol, side),
            ).fetchone()
            con.close()
            if row and row[0]:
                return MZ
    except Exception:
        pass

    return YETIM


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
