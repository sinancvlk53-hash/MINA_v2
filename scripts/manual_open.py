#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manuel pozisyon aç — slot limiti + anayasa marjini.

Örnek:
  python scripts/manual_open.py --symbol BTCUSDT --side LONG
  python scripts/manual_open.py --symbol ETHUSDT --side SHORT --leverage 4 --source haluk
"""
from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL
from config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal
from mina_slot_policy import SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR, SLOT_TOTAL
from mina_entry_orders import register_pending_limit, resolve_entry_order
from mina_signal_source import MANUEL
import mina_tracking as mt

LEVERAGE_DEFAULT = 4
ENTRY_SLOT_RATIO = 0.20
ALLOWED_LEVERAGES = frozenset({1, 2, 3, 4, 5, 10})


def _count_motor_slots(client) -> tuple[int, int, int]:
    """haluk_used, merter_used, total_open."""
    positions = client.futures_position_information()
    haluk = merter = total = 0
    merter_state_path = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
    merter_syms = set()
    if os.path.isfile(merter_state_path):
        import json
        st = json.load(open(merter_state_path, encoding="utf-8"))
        for p in (st.get("positions") or {}).values():
            if p.get("symbol"):
                merter_syms.add(p["symbol"])

    for p in positions:
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        lev = int(p.get("leverage") or 0)
        sym = p["symbol"]
        side = "LONG" if amt > 0 else "SHORT"
        total += 1
        if lev == 1 and side == "LONG" and sym in merter_syms:
            continue  # Merter DCA ayrı slot
        # Manuel / motor 4x — kaynak bilinmiyorsa haluk say
        merter += 0  # motor merter slotu queue'dan gelir
        haluk += 1
    return haluk, merter, total


def slot_check(client, source: str) -> tuple[bool, str]:
    haluk, _, total = _count_motor_slots(client)
    if total >= SLOT_TOTAL:
        return False, f"SLOT_TOTAL {total}/{SLOT_TOTAL}"
    if source == "merter" and haluk >= SLOTS_MERTER_MOTOR:
        return False, f"Merter motor slot dolu"
    if source == "haluk" and haluk >= SLOTS_HALUK_MOTOR:
        return False, f"Haluk motor slot dolu ({SLOTS_HALUK_MOTOR})"
    return True, "OK"


def main() -> None:
    ap = argparse.ArgumentParser(description="MINA manuel pozisyon aç")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    ap.add_argument("--leverage", type=int, default=LEVERAGE_DEFAULT)
    ap.add_argument("--source", default="haluk", choices=["haluk", "merter"])
    ap.add_argument("--entry-price", type=float, default=None, help="Giriş fiyatı (limit/market seçimi)")
    args = ap.parse_args()

    if args.leverage not in ALLOWED_LEVERAGES:
        allowed = ", ".join(f"{x}x" for x in sorted(ALLOWED_LEVERAGES))
        print(f"RED: Geçersiz kaldıraç {args.leverage}x — izin verilen: {allowed}")
        sys.exit(1)

    try:
        from mina_dashboard_settings import is_motor_paused
        if is_motor_paused():
            print("RED: Motor pasif (dashboard ayarları)")
            sys.exit(1)
    except ImportError:
        pass

    symbol = args.symbol.upper()
    side = args.side.upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    client = BinanceConfig().get_client()
    ok, reason = slot_check(client, args.source)
    if not ok:
        print(f"RED: {reason}")
        sys.exit(1)

    try:
        from mina_coin_lock import check_motor_can_open
        lock_reason = check_motor_can_open(symbol, client, ROOT)
        if lock_reason:
            print(f"RED: {lock_reason}")
            sys.exit(1)
    except ImportError:
        pass

    account = AccountManager(client)
    slot = account.calculate_slot_size()
    margin = slot * ENTRY_SLOT_RATIO
    journal = TradingJournal(os.path.join(ROOT, "mina_trading_journal.db"))
    mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception:
        pass
    try:
        client.futures_change_leverage(symbol=symbol, leverage=args.leverage)
    except Exception:
        pass

    mark = float(client.futures_mark_price(symbol=symbol)["markPrice"])
    order_type, limit_px = resolve_entry_order(side, args.entry_price, mark)
    use_limit = order_type == ORDER_TYPE_LIMIT and limit_px is not None
    exec_price = limit_px if use_limit else mark

    notional = margin * args.leverage
    qty = mina._round_quantity(notional / exec_price, symbol)
    if qty <= 0:
        print("RED: miktar sıfır")
        sys.exit(1)

    order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
    if use_limit:
        limit_px = mina._round_price(limit_px)
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_LIMIT,
            price=limit_px,
            quantity=qty,
            positionSide=side,
            timeInForce="GTC",
        )
        pos_key = mt.pos_key(symbol, side)
        register_pending_limit(
            pos_key,
            order_id=int(order.get("orderId") or 0),
            symbol=symbol,
            side=side,
            limit_price=float(limit_px),
            margin=margin,
            leverage=args.leverage,
            meta={"source": "manual_open", "signal_source": MANUEL},
        )
        print(
            f"LIMIT {symbol} {side} @{limit_px} mark={mark:.6f} "
            f"margin={margin:.4f} qty={qty} orderId={order.get('orderId')}"
        )
        print("Tracking limit dolduğunda motor döngüsü seed edecek.")
        return

    order = client.futures_create_order(
        symbol=symbol,
        side=order_side,
        type=ORDER_TYPE_MARKET,
        quantity=qty,
        positionSide=side,
    )
    time.sleep(0.2)
    mark = float(client.futures_mark_price(symbol=symbol)["markPrice"])

    key = mt.pos_key(symbol, side)
    for fname, data in (
        (mt.INITIAL_PRICE_FILE, {key: mark}),
        (mt.INITIAL_MARGIN_FILE, {key: round(margin, 4)}),
        (mt.DEFENSE_FILE, {key: 0}),
        (mt.TP_FILE, {key: 0}),
        (mt.MAX_PRICE_FILE, {key: mark}),
    ):
        d = mt.load_json(fname)
        d.update(data)
        mt.save_json(fname, d)

    mina.init_position_state(symbol, mark)
    st = mina.position_states.get(symbol, {})
    st["initial_margin"] = margin
    mina._save_state()
    mina.log_position_open(symbol, side, args.leverage, mark, qty, margin, signal_source=MANUEL)
    print(f"orderId={order.get('orderId')} trade_id={mina.trade_ids.get(key)}")


if __name__ == "__main__":
    main()
