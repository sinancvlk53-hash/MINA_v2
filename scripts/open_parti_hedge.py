#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PARTIUSDT LONG + SHORT hedge aç (4x isolated, sabit marjin)."""
import os
import sys
import time

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from decimal import Decimal, ROUND_DOWN
from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL
from config import BinanceConfig
from open_fast_coins import LEVERAGE, get_step_sizes, set_isolated_4x, format_qty

SYMBOL = "PARTIUSDT"
MARGIN_USDT = 82.59


def main():
    client = BinanceConfig().get_client()
    print(f"BINANCE TESTNET — {SYMBOL} hedge aç")
    print(f"MARGIN={MARGIN_USDT} USDT | LEVERAGE={LEVERAGE}x ISOLATED\n")

    try:
        client.futures_change_position_mode(dualSidePosition="true")
        print("HEDGE_MODE=OK")
    except Exception as e:
        print(f"HEDGE_MODE={e}")

    step_sizes = get_step_sizes(client)
    if SYMBOL not in step_sizes:
        print(f"ERR: {SYMBOL} futures'ta bulunamadı veya TRADING değil")
        sys.exit(1)

    set_isolated_4x(client, SYMBOL)
    time.sleep(0.2)

    ticker = client.futures_symbol_ticker(symbol=SYMBOL)
    price = Decimal(str(ticker["price"]))
    step = step_sizes[SYMBOL]
    notional = Decimal(str(MARGIN_USDT)) * LEVERAGE
    qty = format_qty(notional / price, step)
    if qty <= 0:
        print(f"ERR: qty sıfır (price={price})")
        sys.exit(1)

    print(f"PRICE={price} QTY={qty} NOTIONAL≈{float(qty * price):.2f} USDT\n")

    for side, order_side in (("LONG", SIDE_BUY), ("SHORT", SIDE_SELL)):
        try:
            order = client.futures_create_order(
                symbol=SYMBOL,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=float(qty),
                positionSide=side,
            )
            print(
                f"OK  {SYMBOL} {side:<5} qty={qty} orderId={order.get('orderId')} "
                f"status={order.get('status')} avgPrice={order.get('avgPrice', '—')}"
            )
        except Exception as e:
            print(f"ERR {SYMBOL} {side:<5} {e}")
        time.sleep(0.3)

    print("\n--- AÇIK POZİSYONLAR (PARTI) ---")
    for p in client.futures_position_information():
        if p["symbol"] != SYMBOL:
            continue
        amt = float(p.get("positionAmt", 0))
        if amt == 0:
            continue
        ps = "LONG" if amt > 0 else "SHORT"
        print(
            f"  {ps:<5} amt={abs(amt)} entry={p.get('entryPrice')} "
            f"mark={p.get('markPrice')} margin={p.get('isolatedMargin')} lev={p.get('leverage')}"
        )


if __name__ == "__main__":
    main()
