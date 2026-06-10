# -*- coding: utf-8 -*-
"""Orphan emir tespiti — Merter DCA parçalı limitler + Haluk PDF duplicate/stale."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MERTER_STATE = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")

# Merter DCA: çok parçalı BUY limit (Haluk PDF genelde tek limit)
MERTER_ORPHAN_MIN_BUY_LIMITS = 2
DEFAULT_STALE_HALUK_SEC = 24 * 3600


def _log_msg(log: Callable[[str], Any], msg: str) -> None:
    log(msg)


def load_merter_state(path: Optional[str] = None) -> Dict[str, Any]:
    path = path or DEFAULT_MERTER_STATE
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"positions": {}}


def merter_state_symbols(state: Dict[str, Any]) -> Set[str]:
    syms: Set[str] = set()
    for pos in (state.get("positions") or {}).values():
        if isinstance(pos, dict) and pos.get("symbol"):
            syms.add(str(pos["symbol"]).upper())
    return syms


def open_position_side_keys(client) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for p in client.futures_position_information():
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        side = "LONG" if amt > 0 else "SHORT"
        keys.add((str(p["symbol"]).upper(), side))
    return keys


def has_open_position_side(client, symbol: str, side: str) -> bool:
    sym = str(symbol).upper()
    side = str(side).upper()
    for p in client.futures_position_information(symbol=sym):
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        pos_side = "LONG" if amt > 0 else "SHORT"
        if pos_side == side:
            return True
    return False


def has_pending_limit_order(client, symbol: str, side: str) -> bool:
    sym = str(symbol).upper()
    side = str(side).upper()
    order_side = "BUY" if side == "LONG" else "SELL"
    try:
        orders = client.futures_get_open_orders(symbol=sym)
    except Exception:
        orders = []
    for o in orders:
        if str(o.get("type", "")).upper() != "LIMIT":
            continue
        if str(o.get("side", "")).upper() == order_side:
            return True
    return False


def haluk_entry_duplicate_reason(client, symbol: str, side: str) -> Optional[str]:
    """Haluk/PDF giriş öncesi duplicate kontrol."""
    if has_open_position_side(client, symbol, side):
        return "zaten açık pozisyon"
    if has_pending_limit_order(client, symbol, side):
        return "bekleyen limit emir var"
    return None


def cancel_merter_orphan_orders(
    client,
    state: Optional[Dict[str, Any]] = None,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """
    State'te kayıtlı olmayan sembollerdeki Merter DCA orphan limitlerini iptal et.
    (2+ BUY LIMIT = Merter parça pattern; tek BUY Haluk PDF olabilir.)
    """
    state = state if state is not None else load_merter_state()
    tracked = merter_state_symbols(state)
    cancelled: List[Dict[str, Any]] = []

    try:
        all_orders = client.futures_get_open_orders()
    except Exception as exc:
        _log_msg(log, f"[ORPHAN] Merter tarama hatası: {exc}")
        return cancelled

    by_sym: Dict[str, List[Dict]] = defaultdict(list)
    for o in all_orders:
        by_sym[str(o["symbol"]).upper()].append(o)

    for sym, sym_orders in by_sym.items():
        if sym in tracked:
            continue
        buy_limits = [
            o for o in sym_orders
            if str(o.get("side", "")).upper() == "BUY"
            and str(o.get("type", "")).upper() == "LIMIT"
        ]
        if len(buy_limits) < MERTER_ORPHAN_MIN_BUY_LIMITS:
            continue
        for o in buy_limits:
            try:
                client.futures_cancel_order(symbol=sym, orderId=o["orderId"])
                cancelled.append(o)
                _log_msg(
                    log,
                    f"[ORPHAN] Merter iptal {sym} orderId={o['orderId']} "
                    f"price={o.get('price')} (state yok, {len(buy_limits)} BUY limit)",
                )
            except Exception as exc:
                _log_msg(log, f"[ORPHAN] Merter iptal hata {sym} #{o.get('orderId')}: {exc}")
    return cancelled


def cancel_duplicate_limits_for_positions(
    client,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """Açık pozisyon varken aynı yönde kalan limit emirleri iptal (LINK duplicate)."""
    pos_keys = open_position_side_keys(client)
    cancelled: List[Dict[str, Any]] = []

    try:
        all_orders = client.futures_get_open_orders()
    except Exception as exc:
        _log_msg(log, f"[ORPHAN] Duplicate tarama hatası: {exc}")
        return cancelled

    for o in all_orders:
        if str(o.get("type", "")).upper() != "LIMIT":
            continue
        sym = str(o["symbol"]).upper()
        side = "LONG" if str(o.get("side", "")).upper() == "BUY" else "SHORT"
        if (sym, side) not in pos_keys:
            continue
        try:
            client.futures_cancel_order(symbol=sym, orderId=o["orderId"])
            cancelled.append(o)
            _log_msg(
                log,
                f"[ORPHAN] Duplicate limit iptal {sym} {side} "
                f"orderId={o['orderId']} price={o.get('price')}",
            )
        except Exception as exc:
            _log_msg(log, f"[ORPHAN] Duplicate iptal hata {sym}: {exc}")
    return cancelled


def cancel_stale_haluk_limits(
    client,
    max_age_sec: int = DEFAULT_STALE_HALUK_SEC,
    state: Optional[Dict[str, Any]] = None,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """
    Pozisyona dönüşmemiş, max_age_sec'ten eski limit emirleri iptal et.
    Merter çoklu BUY limit pattern'i cancel_merter_orphan_orders'a bırakılır.
    """
    state = state if state is not None else load_merter_state()
    tracked = merter_state_symbols(state)
    pos_keys = open_position_side_keys(client)
    now_ms = time.time() * 1000
    cancelled: List[Dict[str, Any]] = []

    try:
        all_orders = client.futures_get_open_orders()
    except Exception as exc:
        _log_msg(log, f"[ORPHAN] Stale tarama hatası: {exc}")
        return cancelled

    by_sym: Dict[str, List[Dict]] = defaultdict(list)
    for o in all_orders:
        if str(o.get("type", "")).upper() != "LIMIT":
            continue
        by_sym[str(o["symbol"]).upper()].append(o)

    for sym, sym_orders in by_sym.items():
        buy_limits = [o for o in sym_orders if str(o.get("side", "")).upper() == "BUY"]
        if sym not in tracked and len(buy_limits) >= MERTER_ORPHAN_MIN_BUY_LIMITS:
            continue

        for o in sym_orders:
            side = "LONG" if str(o.get("side", "")).upper() == "BUY" else "SHORT"
            if (sym, side) in pos_keys:
                continue
            order_time = int(o.get("time") or 0)
            if not order_time:
                continue
            age_ms = now_ms - order_time
            if age_ms < max_age_sec * 1000:
                continue
            try:
                client.futures_cancel_order(symbol=sym, orderId=o["orderId"])
                cancelled.append(o)
                age_h = round(age_ms / 3600000, 1)
                _log_msg(
                    log,
                    f"[ORPHAN] Stale Haluk/PDF iptal {sym} {side} "
                    f"orderId={o['orderId']} price={o.get('price')} age={age_h}h",
                )
            except Exception as exc:
                _log_msg(log, f"[ORPHAN] Stale iptal hata {sym}: {exc}")
    return cancelled


def run_full_orphan_cleanup(
    client,
    *,
    log: Callable[[str], Any] = print,
    stale_sec: int = DEFAULT_STALE_HALUK_SEC,
) -> Dict[str, int]:
    state = load_merter_state()
    merter = cancel_merter_orphan_orders(client, state, log=log)
    dup = cancel_duplicate_limits_for_positions(client, log=log)
    stale = cancel_stale_haluk_limits(client, stale_sec, state, log=log)
    summary = {
        "merter_orphan": len(merter),
        "duplicate_limit": len(dup),
        "stale_haluk": len(stale),
        "total": len(merter) + len(dup) + len(stale),
    }
    _log_msg(
        log,
        f"[ORPHAN] Özet {datetime.now(timezone.utc).isoformat()} "
        f"merter={summary['merter_orphan']} duplicate={summary['duplicate_limit']} "
        f"stale={summary['stale_haluk']} total={summary['total']}",
    )
    return summary
