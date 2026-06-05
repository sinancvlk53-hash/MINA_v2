# -*- coding: utf-8 -*-
"""Giriş emri tipi seçimi (limit vs market) ve bekleyen limit takibi."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET

import mina_tracking as mt

PENDING_TTL_H = 8  # varsayılan; dashboard_settings.halukTimeStopH ile override


def _pending_ttl_h() -> float:
    try:
        from mina_dashboard_settings import haluk_time_stop_h
        return haluk_time_stop_h()
    except Exception:
        return PENDING_TTL_H


def resolve_entry_order(
    side: str,
    entry_price: Optional[float],
    mark: float,
) -> Tuple[str, Optional[float]]:
    """
    LONG: giriş < mark → LIMIT (GTC), aksi halde MARKET.
    SHORT: giriş > mark → LIMIT, aksi halde MARKET.
    Giriş fiyatı yoksa MARKET.
    """
    if entry_price is None or entry_price <= 0:
        return ORDER_TYPE_MARKET, None
    side = side.upper()
    if side == "LONG" and entry_price < mark:
        return ORDER_TYPE_LIMIT, entry_price
    if side == "SHORT" and entry_price > mark:
        return ORDER_TYPE_LIMIT, entry_price
    return ORDER_TYPE_MARKET, None


def register_pending_limit(
    pos_key: str,
    *,
    order_id: int,
    symbol: str,
    side: str,
    limit_price: float,
    margin: float,
    leverage: int,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    pending[pos_key] = {
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "limit_price": limit_price,
        "margin": margin,
        "leverage": leverage,
        "placed_at": time.time(),
        "meta": meta or {},
    }
    mt.save_json(mt.PENDING_ORDERS_FILE, pending)


def pop_pending(pos_key: str) -> Optional[Dict[str, Any]]:
    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    info = pending.pop(pos_key, None)
    if info is not None:
        mt.save_json(mt.PENDING_ORDERS_FILE, pending)
    return info


def cancel_stale_pending_limits(client) -> int:
    """48 saat dolmuş bekleyen limit emirlerini iptal et."""
    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    if not pending:
        return 0
    now = time.time()
    removed = 0
    for pos_key, info in list(pending.items()):
        placed = float(info.get("placed_at") or 0)
        if now - placed < _pending_ttl_h() * 3600:
            continue
        symbol = info.get("symbol")
        oid = info.get("order_id")
        try:
            if symbol and oid:
                client.futures_cancel_order(symbol=symbol, orderId=oid)
        except Exception:
            pass
        pending.pop(pos_key, None)
        removed += 1
    if removed:
        mt.save_json(mt.PENDING_ORDERS_FILE, pending)
    return removed


def process_pending_limit_fills(manager) -> int:
    """
    Bekleyen limit emirleri doldu mu kontrol et; dolmuşsa tracking seed + journal.
    manager: MinaPositionManager
    """
    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    if not pending:
        return 0

    filled = 0
    changed = False
    for pos_key, info in list(pending.items()):
        symbol = info.get("symbol")
        side = str(info.get("side", "")).upper()
        if not symbol or side not in ("LONG", "SHORT"):
            pending.pop(pos_key, None)
            changed = True
            continue

        if mt.pos_key(symbol, side) in mt.load_json(mt.INITIAL_MARGIN_FILE):
            pending.pop(pos_key, None)
            changed = True
            continue

        try:
            rows = manager.client.futures_position_information(symbol=symbol)
        except Exception:
            continue

        amt = 0.0
        entry = 0.0
        for p in rows:
            a = float(p.get("positionAmt") or 0)
            if a == 0:
                continue
            ps = p.get("positionSide", "BOTH")
            pos_side = side if ps in (side, "BOTH") else None
            if ps == "BOTH":
                pos_side = "LONG" if a > 0 else "SHORT"
            if pos_side == side:
                amt = abs(a)
                entry = float(p.get("entryPrice") or 0)
                break

        if amt <= 0 or entry <= 0:
            continue

        margin = float(info.get("margin") or 0)
        leverage = int(info.get("leverage") or 4)
        src = (info.get("meta") or {}).get("signal_source", "HT")
        from signal_bot.signal_slot_bridge import _mark_consumed, load_queue, _seed_tracking

        _seed_tracking(manager, symbol, side, entry, margin)
        manager.log_position_open(
            symbol=symbol,
            side=side,
            leverage=leverage,
            entry_price=entry,
            qty=amt,
            initial_margin=margin,
            signal_source=src,
        )

        meta = info.get("meta") or {}
        fp = meta.get("fingerprint")
        if fp:
            queue = load_queue()
            _mark_consumed(queue, fp, {
                "symbol": symbol,
                "side": side,
                "entry_price": entry,
                "qty": amt,
                "order_type": "LIMIT",
                "filled_from_pending": True,
            })

        pending.pop(pos_key, None)
        changed = True
        filled += 1
        print(
            f"[PENDING_LIMIT] Doldu {symbol} {side} entry={entry:.6f} "
            f"qty={amt} order={info.get('order_id')}"
        )

    if changed:
        mt.save_json(mt.PENDING_ORDERS_FILE, pending)
    return filled
