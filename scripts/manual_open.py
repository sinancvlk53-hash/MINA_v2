#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manuel pozisyon aç — otomatik slot + anayasa marjini.

Kaldıraç yönlendirme:
  1x  → ilk boş Merter DCA yuvası
  2–10x → ilk boş motor slotu (4x dahil)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL
from config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal
from mina_manual_slot import check_manual_slot, slot_target_for_leverage
from mina_entry_orders import register_pending_limit, resolve_entry_order
from mina_signal_source import MANUEL
import mina_tracking as mt

LEVERAGE_DEFAULT = 4
ENTRY_SLOT_RATIO = 0.20
ALLOWED_LEVERAGES = frozenset({1, 2, 3, 4, 5, 10})


def _api_error_text(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    if code is not None:
        return f"Binance API error {code}: {message}"
    return f"{type(exc).__name__}: {message}"


def _open_merter_manual(symbol: str, yuva: str) -> None:
    from signal_bot.merter_dca_manager import MerterDCAManager

    mgr = MerterDCAManager(data_root=ROOT)
    ok = mgr.open_dca_position(symbol, yuva, initial_parts=1, skip_filters=True)
    if not ok:
        print(f"RED: Merter DCA açılışı başarısız ({yuva})")
        sys.exit(1)
    print(f"OK: Merter DCA {symbol} → {yuva} (1/10 parça)")


def _prepare_symbol(client, symbol: str, leverage: int) -> None:
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception as exc:
        print(f"WARN: margin type: {_api_error_text(exc)}")
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except Exception as exc:
        print(f"WARN: leverage: {_api_error_text(exc)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="MINA manuel pozisyon aç")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    ap.add_argument("--leverage", type=int, default=LEVERAGE_DEFAULT)
    ap.add_argument("--entry-price", type=float, default=None, help="Giriş fiyatı (limit)")
    ap.add_argument("--stop-price", type=float, default=None, help="Tetik fiyatı (stop market)")
    ap.add_argument(
        "--order-type",
        default="market",
        choices=["market", "limit", "stop_market"],
        help="Emir tipi",
    )
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
    ok, slot_msg, slot_ref = check_manual_slot(client, args.leverage, side)
    if not ok:
        print(f"RED: {slot_msg}")
        sys.exit(1)

    target = slot_target_for_leverage(args.leverage)
    if target == "merter":
        if args.order_type != "market":
            print("RED: Merter DCA manuel açılış yalnızca Market emir destekler")
            sys.exit(1)
        print(f"SLOT: {slot_msg}")
        _open_merter_manual(symbol, str(slot_ref))
        return

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
    try:
        from mina_dashboard_settings import entry_margin_for_leverage
        margin = entry_margin_for_leverage(args.leverage, slot)
    except ImportError:
        margin = slot * ENTRY_SLOT_RATIO
    journal = TradingJournal(os.path.join(ROOT, "mina_trading_journal.db"))
    mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    _prepare_symbol(client, symbol, args.leverage)
    print(f"SLOT: {slot_msg}")

    try:
        mark = float(client.futures_mark_price(symbol=symbol)["markPrice"])
    except Exception as exc:
        print(f"RED: Mark fiyat okunamadı: {_api_error_text(exc)}")
        sys.exit(1)

    order_type = (args.order_type or "market").lower()
    use_stop = order_type == "stop_market"
    use_limit = order_type == "limit"

    if use_stop:
        if args.stop_price is None or args.stop_price <= 0:
            print("RED: Stop Market için geçerli --stop-price gerekli")
            sys.exit(1)
        stop_px = mina._round_price(args.stop_price)
        exec_price = stop_px
    elif use_limit:
        if args.entry_price is None or args.entry_price <= 0:
            print("RED: Limit için geçerli --entry-price gerekli")
            sys.exit(1)
        resolved_type, limit_px = resolve_entry_order(side, args.entry_price, mark)
        if resolved_type != ORDER_TYPE_LIMIT or limit_px is None:
            print(
                f"RED: Limit emir uygun değil (mark={mark:.6f}, giriş={args.entry_price}) — "
                "LONG için mark altı, SHORT için mark üstü girin veya Market seçin"
            )
            sys.exit(1)
        exec_price = limit_px
    else:
        limit_px = None
        exec_price = mark

    notional = margin * args.leverage
    qty = mina._round_quantity(notional / exec_price, symbol)
    if qty <= 0:
        print(f"RED: miktar sıfır (margin={margin:.4f} notional={notional:.4f} price={exec_price})")
        sys.exit(1)

    min_notional = 20.0
    if notional < min_notional:
        print(
            f"RED: Notional {notional:.2f} USDT < minimum {min_notional:.0f} USDT "
            f"(kasa/slot çok düşük olabilir)"
        )
        sys.exit(1)

    order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
    try:
        if use_stop:
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type="STOP_MARKET",
                stopPrice=stop_px,
                quantity=qty,
                positionSide=side,
            )
            pos_key = mt.pos_key(symbol, side)
            register_pending_limit(
                pos_key,
                order_id=int(order.get("orderId") or 0),
                symbol=symbol,
                side=side,
                limit_price=float(stop_px),
                margin=margin,
                leverage=args.leverage,
                meta={"source": "manual_open", "signal_source": MANUEL, "order_type": "STOP_MARKET"},
            )
            print(
                f"STOP_MARKET {symbol} {side} stop={stop_px} mark={mark:.6f} "
                f"margin={margin:.4f} qty={qty} orderId={order.get('orderId')}"
            )
            print("Tracking tetiklenince motor döngüsü seed edecek.")
            return

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
    except Exception as exc:
        print(f"RED: Emir reddedildi: {_api_error_text(exc)}")
        traceback.print_exc()
        sys.exit(1)

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
    print(f"OK: Motor {symbol} {side} {args.leverage}x")
    print(f"orderId={order.get('orderId')} trade_id={mina.trade_ids.get(key)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RED: {_api_error_text(exc)}")
        traceback.print_exc()
        sys.exit(1)
