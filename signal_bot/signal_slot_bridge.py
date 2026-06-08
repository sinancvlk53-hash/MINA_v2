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
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

import mina_tracking as mt
from mina_entry_orders import (
    register_pending_limit,
    resolve_entry_order,
)
from mina_signal_source import queue_source_to_code
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
from mina_slot_policy import MOTOR_SLOT_MAX, SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR

MAX_POSITIONS = MOTOR_SLOT_MAX
QUEUE_TTL_SEC = 30 * 60  # Sinyal kuyrukta max 30 dakika


def _is_haluk_entry(entry: Dict[str, Any]) -> bool:
    return str(entry.get("source") or "").lower().startswith("haluk")


def _haluk_reject(symbol: str, reason: str) -> None:
    try:
        from mina_motor_telegram import notify_haluk_slot_reject
        notify_haluk_slot_reject(symbol, reason)
    except Exception as exc:
        print(f"[SLOT_BRIDGE] Haluk reddi Telegram: {exc}")


def _haluk_reject_if(entry: Dict[str, Any], reason: str) -> None:
    if _is_haluk_entry(entry):
        _haluk_reject(str(entry.get("symbol") or ""), reason)


def _haluk_tp_prices(entry_price: float, side: str) -> Tuple[float, float]:
    if side == "LONG":
        return entry_price * 1.03, entry_price * 1.05
    return entry_price * 0.97, entry_price * 0.95


def _get_bridge_manager() -> Optional["MinaPositionManager"]:
    try:
        from signal_bot.signal_parser import _get_binance_client
        from config import AccountManager
        from mina_position_manager import MinaPositionManager
        from mina_trading_journal import TradingJournal

        client = _get_binance_client()
        account = AccountManager(client)
        slot = account.calculate_slot_size()
        root = os.environ.get("MINA_DATA_ROOT", _ROOT)
        db_path = os.path.join(root, "mina_trading_journal.db")
        journal = TradingJournal(db_path=db_path)
        return MinaPositionManager(client, slot, journal=journal, data_root=root)
    except Exception as exc:
        print(f"[SLOT_BRIDGE] Manager oluşturulamadı: {exc}")
        return None


def try_open_haluk_entry(entry: Dict[str, Any]) -> None:
    """Haluk onaylı AL sinyali gelince hemen 4x açmayı dene."""
    if not _is_haluk_entry(entry) or entry.get("status") != "approved":
        return
    symbol = str(entry.get("symbol") or "")
    side = str(entry.get("direction") or "").upper()
    if not symbol or side not in ("LONG", "SHORT"):
        return

    queue = load_queue()
    scored = score_entry(entry, queue)
    if not scored:
        _haluk_reject(symbol, "filtre veya guillotine reddi")
        return

    manager = _get_bridge_manager()
    if not manager:
        return

    if mt.pos_key(symbol, side) in _open_position_keys(manager.client):
        _haluk_reject(symbol, "zaten açık pozisyon")
        return

    open_signal_position(manager, scored, queue)


def schedule_haluk_open_attempt(entry: Dict[str, Any]) -> None:
    """Listener thread'inden Haluk açılışını arka planda tetikle."""
    if not _is_haluk_entry(entry) or entry.get("status") != "approved":
        return

    def _run() -> None:
        try:
            try_open_haluk_entry(entry)
        except Exception as exc:
            print(f"[SLOT_BRIDGE] Haluk açılış hatası {entry.get('symbol')}: {exc}")

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"haluk-open-{entry.get('symbol')}",
    ).start()


def _parse_entry_ts(entry: Dict[str, Any]) -> Optional[float]:
    """Entry timestamp → unix saniye (UTC)."""
    raw = entry.get("timestamp")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            return float(raw)
        s = str(raw).strip().replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def expire_stale_queue_entries(
    queue: Optional[Dict[str, Any]] = None,
    *,
    save: bool = True,
) -> int:
    """
    30 dakikadan eski onaylı, tüketilmemiş sinyalleri iptal et.
    Slot köprüsü bu kayıtları kullanmaz.
    """
    queue = queue or load_queue()
    now = time.time()
    expired = 0
    changed = False
    for entry in queue.get("entries") or []:
        if entry.get("queue_state") in ("consumed", "cancelled", "superseded"):
            continue
        if entry.get("status") != "approved":
            continue
        ts = _parse_entry_ts(entry)
        if ts is None:
            continue
        age_sec = now - ts
        if age_sec <= QUEUE_TTL_SEC:
            continue
        entry["queue_state"] = "cancelled"
        entry["cancel_reason"] = "queue_ttl_30m"
        entry["cancelled_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry["queue_age_min"] = round(age_sec / 60, 1)
        expired += 1
        changed = True
        sym = entry.get("symbol", "?")
        print(
            f"[SLOT_BRIDGE] Kuyruk iptal (30m TTL): {sym} {entry.get('direction')} "
            f"ts={entry.get('timestamp')} age={entry['queue_age_min']}dk"
        )
    if changed and save:
        save_queue(queue)
    return expired


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
    if entry.get("queue_state") in ("consumed", "cancelled", "superseded", "expired"):
        return False
    ts = _parse_entry_ts(entry)
    if ts is not None and (time.time() - ts) > QUEUE_TTL_SEC:
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
    expire_stale_queue_entries(queue, save=True)
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
    """Seçilen sinyal için MARKET veya LIMIT giriş + tracking seed."""
    try:
        from mina_dashboard_settings import is_motor_paused, is_new_entries_blocked
        if is_motor_paused():
            _haluk_reject_if(entry, "motor duraklatıldı")
            return None
        if is_new_entries_blocked():
            print("[SLOT_BRIDGE] Reddedildi: günlük zarar kill-switch aktif")
            _haluk_reject_if(entry, "kill-switch aktif")
            return None
    except ImportError:
        pass
    from config import AccountManager

    entry = scored["entry"]
    symbol = str(entry["symbol"])
    side = str(entry["direction"]).upper()
    signal_entry = entry.get("entry_price")
    if signal_entry is not None:
        try:
            signal_entry = float(signal_entry)
        except (TypeError, ValueError):
            signal_entry = None

    account = AccountManager(manager.client)
    manager.slot_size = account.calculate_slot_size()
    try:
        from mina_dashboard_settings import entry_margin_for_leverage
        margin = entry_margin_for_leverage(LEVERAGE, manager.slot_size)
    except ImportError:
        margin = manager.slot_size * ENTRY_SLOT_RATIO

    ok, reason = _slot_limit_check(manager.client, symbol, side, margin)
    if not ok:
        print(f"[SLOT_BRIDGE] Reddedildi {symbol} {side}: {reason}")
        _haluk_reject_if(entry, reason)
        return None

    try:
        from mina_coin_lock import check_motor_can_open
        lock_reason = check_motor_can_open(symbol, manager.client)
        if lock_reason:
            print(f"[SLOT_BRIDGE] Reddedildi {symbol} {side}: {lock_reason}")
            _haluk_reject_if(entry, lock_reason)
            return None
    except ImportError:
        pass

    _prepare_symbol(manager.client, symbol)
    time.sleep(0.15)

    try:
        mark = float(manager.client.futures_mark_price(symbol=symbol)["markPrice"])
    except Exception as e:
        print(f"[SLOT_BRIDGE] Fiyat okunamadı {symbol}: {e}")
        _haluk_reject_if(entry, f"fiyat okunamadı: {e}")
        return None

    order_type, limit_px = resolve_entry_order(side, signal_entry, mark)
    use_limit = order_type == ORDER_TYPE_LIMIT and limit_px is not None
    exec_price = limit_px if use_limit else mark

    notional = margin * LEVERAGE
    qty = manager._round_quantity(notional / exec_price, symbol)
    if qty <= 0:
        print(f"[SLOT_BRIDGE] Miktar sıfır {symbol} margin={margin:.4f} mark={mark}")
        _haluk_reject_if(entry, "miktar sıfır")
        return None

    order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
    limit_px = manager._round_price(limit_px) if use_limit else None
    try:
        if use_limit:
            order = manager.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_LIMIT,
                price=limit_px,
                quantity=qty,
                positionSide=side,
                timeInForce="GTC",
            )
        else:
            order = manager.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=qty,
                positionSide=side,
            )
    except Exception as e:
        print(f"[SLOT_BRIDGE] Emir hatası {symbol} {side}: {e}")
        _haluk_reject_if(entry, f"emir hatası: {e}")
        return None

    pos_key = mt.pos_key(symbol, side)
    src_code = queue_source_to_code(entry.get("source"))
    if use_limit:
        register_pending_limit(
            pos_key,
            order_id=int(order.get("orderId") or 0),
            symbol=symbol,
            side=side,
            limit_price=float(limit_px),
            margin=margin,
            leverage=LEVERAGE,
            meta={
                "brightness": scored.get("brightness"),
                "label": scored.get("k2", {}).get("label"),
                "fingerprint": scored.get("fingerprint"),
                "signal_source": src_code,
            },
        )
        queue = queue or load_queue()
        for qe in queue.get("entries") or []:
            if entry_fingerprint(qe) != scored["fingerprint"]:
                continue
            qe["queue_state"] = "pending_limit"
            qe["pending_limit_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            qe["pending_order_id"] = order.get("orderId")
            qe["limit_price"] = limit_px
            break
        save_queue(queue)
        print(
            f"[SLOT_BRIDGE] LIMIT bekliyor {symbol} {side} @{limit_px} "
            f"mark={mark:.6f} order={order.get('orderId')}"
        )
        return {
            "symbol": symbol,
            "side": side,
            "order_type": "LIMIT",
            "limit_price": limit_px,
            "order_id": order.get("orderId"),
            "pending": True,
        }

    try:
        mark_t = manager.client.futures_mark_price(symbol=symbol)
        entry_price = float(mark_t["markPrice"])
    except Exception:
        entry_price = mark

    _seed_tracking(manager, symbol, side, entry_price, margin)
    haluk_open = _is_haluk_entry(entry)
    manager.log_position_open(
        symbol=symbol,
        side=side,
        leverage=LEVERAGE,
        entry_price=entry_price,
        qty=qty,
        initial_margin=margin,
        signal_source=src_code,
        send_telegram=not haluk_open,
    )
    if haluk_open:
        tp1, tp2 = _haluk_tp_prices(entry_price, side)
        try:
            from mina_motor_telegram import notify_haluk_signal_opened
            notify_haluk_signal_opened(symbol, side, entry_price, tp1, tp2, LEVERAGE)
        except Exception as exc:
            print(f"[SLOT_BRIDGE] Haluk Telegram: {exc}")

    meta = {
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "qty": qty,
        "margin": margin,
        "order_id": order.get("orderId"),
        "order_type": "MARKET",
        "brightness": scored.get("brightness"),
        "label": scored.get("k2", {}).get("label"),
        "opened_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    queue = queue or load_queue()
    _mark_consumed(queue, scored["fingerprint"], meta)

    print(
        f"[SLOT_BRIDGE] Açıldı {symbol} {side} MARKET "
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
    expire_stale_queue_entries(queue, save=True)
    scored = pick_best_signal(manager.client, queue)
    if not scored:
        print("[SLOT_BRIDGE] Uygun sinyal yok — slot boş kaldı")
        return None
    return open_signal_position(manager, scored, queue)
