# -*- coding: utf-8 -*-
"""
MINA v2 — Slot doldurma köprüsü (MinaPositionManager ↔ signal_guillotine)

Pozisyon tam kapandığında raw_signal_queue.json içinden en yüksek parlaklıklı
onaylı sinyali seçer ve yeni pozisyon açar.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

import mina_tracking as mt
from signal_bot.signal_guillotine import evaluate_guillotine, evaluate_katman3
from signal_bot.signal_parser import MACRO_FILTER_BASES, load_queue, save_queue
from signal_bot.signal_pipeline import (
    _utc_session,
    entry_fingerprint,
    extract_total_macro_text,
)

if TYPE_CHECKING:
    from mina_position_manager import MinaPositionManager

LEVERAGE = 4
SLOT_COUNT = 10
ENTRY_SLOT_RATIO = 0.20
SLOT_CAP_RATIO = 0.98
MAX_POSITIONS = 10


def _open_position_keys(client) -> Set[str]:
    keys: Set[str] = set()
    for p in client.futures_position_information():
        amt = float(p.get("positionAmt", 0))
        if amt == 0:
            continue
        side = "LONG" if amt > 0 else "SHORT"
        keys.add(mt.pos_key(p["symbol"], side))
    return keys


def _slot_limit_check(
    client,
    symbol: str,
    side: str,
    margin_usdt: float,
) -> Tuple[bool, str]:
    from config import AccountManager

    positions = client.futures_position_information()
    open_count = sum(1 for p in positions if float(p.get("positionAmt", 0)) != 0)
    if open_count >= MAX_POSITIONS:
        return False, f"MAX_POSITIONS {open_count}/{MAX_POSITIONS}"

    account = AccountManager(client)
    fresh_balance = account.get_usdt_balance()
    slot_cap = (fresh_balance / SLOT_COUNT) * SLOT_CAP_RATIO

    current_margin = 0.0
    for p in positions:
        amt = float(p.get("positionAmt", 0))
        if amt == 0:
            continue
        pos_side = "LONG" if amt > 0 else "SHORT"
        if p["symbol"] == symbol and pos_side == side:
            current_margin = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
            break

    projected = current_margin + margin_usdt
    if projected > slot_cap:
        return False, f"MARGIN_CAP projected={projected:.4f} cap={slot_cap:.4f}"
    return True, "OK"


def _is_trade_candidate(entry: Dict[str, Any]) -> bool:
    if entry.get("status") != "approved":
        return False
    if entry.get("queue_state") == "consumed":
        return False
    sym = str(entry.get("symbol", "")).upper()
    if sym in MACRO_FILTER_BASES or sym == "SYSTEM":
        return False
    direction = str(entry.get("direction") or "").upper()
    return direction in ("LONG", "SHORT")


def score_entry(
    entry: Dict[str, Any],
    queue: Dict[str, Any],
    session: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Katman 2+3 skoru; REJECT / SKIP ise None."""
    if not _is_trade_candidate(entry):
        return None

    macro = extract_total_macro_text(queue)
    sess = session or _utc_session()
    raw = entry.get("raw_snippet") or entry.get("raw_text") or ""
    k2 = evaluate_guillotine(
        merter_record=entry,
        haluk_macro_text=macro,
        session=sess,
        merter_raw_text=raw,
    )
    k3 = evaluate_katman3(k2)
    if k2.get("label") == "REJECT" or k3.get("action") == "SKIP":
        return None

    return {
        "entry": entry,
        "fingerprint": entry_fingerprint(entry),
        "k2": k2,
        "k3": k3,
        "brightness": int(k2.get("brightness") or 0),
        "session": sess,
    }


def rank_actionable_signals(
    client,
    queue: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Onaylı, tüketilmemiş, açılmaya uygun sinyalleri parlaklığa göre sırala."""
    queue = queue or load_queue()
    session = _utc_session()
    open_keys = _open_position_keys(client)
    ranked: List[Dict[str, Any]] = []

    for entry in queue.get("entries") or []:
        scored = score_entry(entry, queue, session)
        if not scored:
            continue
        symbol = str(entry.get("symbol", ""))
        side = str(entry.get("direction", "")).upper()
        if mt.pos_key(symbol, side) in open_keys:
            continue
        ranked.append(scored)

    ranked.sort(
        key=lambda x: (
            -x["brightness"],
            str(x["entry"].get("timestamp") or ""),
        ),
    )
    return ranked


def pick_best_signal(
    client,
    queue: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    ranked = rank_actionable_signals(client, queue)
    return ranked[0] if ranked else None


def _mark_consumed(queue: Dict[str, Any], fingerprint: str, meta: Dict[str, Any]) -> None:
    for entry in queue.get("entries") or []:
        if entry_fingerprint(entry) != fingerprint:
            continue
        entry["queue_state"] = "consumed"
        entry["consumed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry["consumed_by"] = "slot_bridge"
        entry["bridge_open"] = meta
        break
    save_queue(queue)


def _prepare_symbol(client, symbol: str) -> None:
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception:
        pass
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass


def _seed_tracking(
    manager: "MinaPositionManager",
    symbol: str,
    side: str,
    entry_price: float,
    margin: float,
) -> None:
    key = manager._pos_key(symbol, side)

    initial_prices = mt.load_json(mt.INITIAL_PRICE_FILE)
    initial_margins = mt.load_json(mt.INITIAL_MARGIN_FILE)
    defense_levels = mt.load_json(mt.DEFENSE_FILE)
    tp_levels = mt.load_json(mt.TP_FILE)
    max_prices = mt.load_json(mt.MAX_PRICE_FILE)

    initial_prices[key] = entry_price
    initial_margins[key] = round(margin, 4)
    defense_levels[key] = 0
    tp_levels[key] = 0
    max_prices[key] = entry_price

    mt.save_json(mt.INITIAL_PRICE_FILE, initial_prices)
    mt.save_json(mt.INITIAL_MARGIN_FILE, initial_margins)
    mt.save_json(mt.DEFENSE_FILE, defense_levels)
    mt.save_json(mt.TP_FILE, tp_levels)
    mt.save_json(mt.MAX_PRICE_FILE, max_prices)

    manager.init_position_state(symbol, entry_price)
    state = manager.position_states.get(symbol, {})
    state["initial_margin"] = margin
    state["defense_stage"] = 0
    state["tp1_done"] = False
    state["tp2_done"] = False
    state["highest_price"] = entry_price
    state["weighted_avg_price"] = entry_price
    manager._save_state()


def open_signal_position(
    manager: "MinaPositionManager",
    scored: Dict[str, Any],
    queue: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Seçilen sinyal için MARKET giriş + tracking seed."""
    from config import AccountManager

    entry = scored["entry"]
    symbol = str(entry["symbol"])
    side = str(entry["direction"]).upper()

    account = AccountManager(manager.client)
    manager.slot_size = account.calculate_slot_size()
    margin = manager.slot_size * ENTRY_SLOT_RATIO

    ok, reason = _slot_limit_check(manager.client, symbol, side, margin)
    if not ok:
        print(f"[SLOT_BRIDGE] Reddedildi {symbol} {side}: {reason}")
        return None

    _prepare_symbol(manager.client, symbol)
    time.sleep(0.15)

    try:
        ticker = manager.client.futures_symbol_ticker(symbol=symbol)
        mark = float(ticker["price"])
    except Exception as e:
        print(f"[SLOT_BRIDGE] Fiyat okunamadı {symbol}: {e}")
        return None

    notional = margin * LEVERAGE
    qty = manager._round_quantity(notional / mark, symbol)
    if qty <= 0:
        print(f"[SLOT_BRIDGE] Miktar sıfır {symbol} margin={margin:.4f} mark={mark}")
        return None

    order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
    try:
        order = manager.client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
            positionSide=side,
        )
    except Exception as e:
        print(f"[SLOT_BRIDGE] Emir hatası {symbol} {side}: {e}")
        return None

    try:
        mark_t = manager.client.futures_mark_price(symbol=symbol)
        entry_price = float(mark_t["markPrice"])
    except Exception:
        entry_price = mark

    _seed_tracking(manager, symbol, side, entry_price, margin)
    manager.log_position_open(
        symbol=symbol,
        side=side,
        leverage=LEVERAGE,
        entry_price=entry_price,
        qty=qty,
        initial_margin=margin,
    )

    meta = {
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "qty": qty,
        "margin": margin,
        "order_id": order.get("orderId"),
        "brightness": scored.get("brightness"),
        "label": scored.get("k2", {}).get("label"),
        "opened_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    queue = queue or load_queue()
    _mark_consumed(queue, scored["fingerprint"], meta)

    print(
        f"[SLOT_BRIDGE] Açıldı {symbol} {side} "
        f"parlaklık={scored.get('brightness')} label={scored.get('k2', {}).get('label')} "
        f"margin={margin:.4f} qty={qty} order={order.get('orderId')}"
    )
    return meta


def try_fill_freed_slot(manager: "MinaPositionManager") -> Optional[Dict[str, Any]]:
    """
    Boşalan slot için kuyruktan en iyi onaylı sinyali al ve pozisyon aç.
    MinaPositionManager.log_position_close sonunda çağrılır.
    """
    queue = load_queue()
    scored = pick_best_signal(manager.client, queue)
    if not scored:
        print("[SLOT_BRIDGE] Uygun sinyal yok — slot boş kaldı")
        return None
    return open_signal_position(manager, scored, queue)
