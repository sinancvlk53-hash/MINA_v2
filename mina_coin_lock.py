# -*- coding: utf-8 -*-
"""Motor ↔ Merter çapraz coin kilidi — aynı sembol iki sistemde açılamaz."""

from __future__ import annotations

import os
import sqlite3
from typing import Optional, Set

import mina_tracking as mt


def _root(data_root: Optional[str] = None) -> str:
    return data_root or os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")


def _json_path(data_root: str, filename: str) -> str:
    return os.path.join(data_root, filename)


def merter_active_symbols(data_root: Optional[str] = None) -> Set[str]:
    """Merter DCA state + DERR'deki 1x Merter kayıtları."""
    root = _root(data_root)
    symbols: Set[str] = set()
    state = mt.load_json(_json_path(root, "signal_bot/merter_dca_state.json"))
    for pos in (state.get("positions") or {}).values():
        sym = (pos.get("symbol") or "").strip().upper()
        if sym:
            symbols.add(sym)

    db_path = _json_path(root, "mina_trading_journal.db")
    if os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout=30000")
            rows = conn.execute(
                """
                SELECT DISTINCT symbol FROM trades
                WHERE status = 'open' AND side = 'LONG' AND leverage = 1
                  AND (signal_source = 'MZ' OR signal_source LIKE 'merter%')
                """
            ).fetchall()
            conn.close()
            for (sym,) in rows:
                if sym:
                    symbols.add(str(sym).upper())
        except Exception:
            pass
    return symbols


def motor_active_symbols(data_root: Optional[str] = None) -> Set[str]:
    """Motor takip dosyaları + bekleyen limit + DERR motor kayıtları."""
    root = _root(data_root)
    symbols: Set[str] = set()
    merter = merter_active_symbols(root)

    for fname in (
        "initial_entry_prices.json",
        "initial_margins.json",
        "defense_levels.json",
        "pending_orders.json",
    ):
        data = mt.load_json(_json_path(root, fname))
        if fname == "pending_orders.json":
            for info in (data or {}).values():
                sym = (info.get("symbol") or "").strip().upper()
                if sym:
                    symbols.add(sym)
        else:
            for key in data or {}:
                sym = str(key).replace("_LONG", "").replace("_SHORT", "").upper()
                if sym and sym not in merter:
                    symbols.add(sym)

    db_path = _json_path(root, "mina_trading_journal.db")
    if os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout=30000")
            rows = conn.execute(
                """
                SELECT DISTINCT symbol FROM trades
                WHERE status = 'open'
                  AND NOT (side = 'LONG' AND leverage = 1
                           AND (signal_source = 'MZ' OR signal_source LIKE 'merter%'))
                """
            ).fetchall()
            conn.close()
            for (sym,) in rows:
                if sym and str(sym).upper() not in merter:
                    symbols.add(str(sym).upper())
        except Exception:
            pass
    return symbols


def _exchange_open_symbols(client) -> Set[str]:
    symbols: Set[str] = set()
    try:
        for p in client.futures_position_information():
            if abs(float(p.get("positionAmt") or 0)) > 0:
                symbols.add(str(p["symbol"]).upper())
    except Exception:
        pass
    return symbols


def check_motor_can_open(
    symbol: str,
    client=None,
    data_root: Optional[str] = None,
) -> Optional[str]:
    """Motor açılışı engellenmişse sebep döner."""
    sym = (symbol or "").upper()
    if sym in merter_active_symbols(data_root):
        return f"{sym} Merter DCA tarafında aktif — motor açılamaz"
    if client is not None:
        open_syms = _exchange_open_symbols(client)
        motor_syms = motor_active_symbols(data_root)
        if sym in open_syms and sym not in motor_syms:
            return f"{sym} borsada açık (Merter?) — motor açılamaz"
    try:
        from mina_dashboard_settings import is_new_entries_blocked
        if is_new_entries_blocked():
            return "Günlük zarar limiti aşıldı — yeni pozisyon açılamaz"
    except ImportError:
        pass
    return None


def check_merter_can_open(
    symbol: str,
    client=None,
    data_root: Optional[str] = None,
) -> Optional[str]:
    """Merter açılışı engellenmişse sebep döner."""
    sym = (symbol or "").upper()
    if sym in motor_active_symbols(data_root):
        return f"{sym} motor tarafında aktif — Merter açılamaz"
    if client is not None:
        open_syms = _exchange_open_symbols(client)
        merter_syms = merter_active_symbols(data_root)
        if sym in open_syms and sym not in merter_syms:
            return f"{sym} borsada açık (motor?) — Merter açılamaz"
    try:
        from mina_dashboard_settings import is_new_entries_blocked
        if is_new_entries_blocked():
            return "Günlük zarar limiti aşıldı — yeni pozisyon açılamaz"
    except ImportError:
        pass
    return None
