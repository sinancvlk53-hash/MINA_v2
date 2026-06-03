# -*- coding: utf-8 -*-
"""
MINA v2 — Hızlı coin açılışı (Testnet)
Dinamik slot: bakiye/10, giriş = slot×0.20, 4x ISOLATED
"""

from __future__ import annotations

import os
import sys
import time
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL
from config import BinanceConfig, AccountManager

LEVERAGE = 4
SLOT_COUNT = 10
ENTRY_SLOT_RATIO = 0.20
SLOT_CAP_RATIO = 0.98
MAX_POSITIONS = 10

LONG_PLAN = [
    ("LABUSDT", "LITUSDT"),
    ("USUSDT", "LITUSDT"),
    ("APREUSDT", "LITUSDT"),
    ("CLOUSDT", "LITUSDT"),
]
SHORT_PLAN = [
    ("ZORAUSDT", "OPENUSDT"),
    ("BBXUSDT", "OPENUSDT"),
    ("ZECUSDT", "OPENUSDT"),
    ("TAUSDT", "OPENUSDT"),
]
HEDGE_PRIMARY = "BEUSDT"
HEDGE_BACKUP_CANDIDATES = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "BTCUSDT"]
STRESS_SYMBOL = "BTCUSDT"


def _slot_limit_check(client, symbol: str, side: str, margin_usdt: float, label: str) -> Tuple[bool, str]:
    """10 pozisyon kapısı + slot marjin tavanı (engine _slot_limit_check uyumlu)."""
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


def get_step_sizes(client) -> dict:
    info = client.futures_exchange_info()
    out = {}
    for s in info["symbols"]:
        if s.get("status") != "TRADING":
            continue
        for f in s.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                out[s["symbol"]] = Decimal(f["stepSize"])
                break
    return out


def format_qty(raw: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return raw.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    prec = abs(step.as_tuple().exponent)
    return raw.quantize(Decimal(1).scaleb(-prec), rounding=ROUND_DOWN)


def ensure_hedge_mode(client) -> None:
    try:
        client.futures_change_position_mode(dualSidePosition="true")
        print("HEDGE_MODE=OK")
    except Exception as e:
        print(f"HEDGE_MODE={e}")


def set_isolated_4x(client, symbol: str) -> None:
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception:
        pass
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass


def find_hedge_backup(client, exclude: set) -> Optional[str]:
    try:
        tickers = client.futures_ticker()
        ranked = sorted(
            [t for t in tickers if t["symbol"].endswith("USDT") and t["symbol"] not in exclude],
            key=lambda x: float(x.get("quoteVolume", 0)),
            reverse=True,
        )
        for t in ranked[:30]:
            sym = t["symbol"]
            if sym in get_step_sizes(client):
                return sym
    except Exception as e:
        print(f"HEDGE_BACKUP_SEARCH_ERR={e}")
    return HEDGE_BACKUP_CANDIDATES[0]


def open_market(
    client,
    symbol: str,
    side: str,
    margin_usdt: float,
    step_sizes: dict,
    label: str,
) -> Optional[dict]:
    ok, reason = _slot_limit_check(client, symbol, side, margin_usdt, label)
    if not ok:
        print(f"SLOT_LIMIT_REJECT symbol={symbol} side={side} reason={reason}")
        return None

    if symbol not in step_sizes:
        raise ValueError(f"SYMBOL_NOT_TRADING symbol={symbol}")

    set_isolated_4x(client, symbol)
    time.sleep(0.15)

    ticker = client.futures_symbol_ticker(symbol=symbol)
    price = Decimal(str(ticker["price"]))
    notional = Decimal(str(margin_usdt)) * LEVERAGE
    qty = format_qty(notional / price, step_sizes[symbol])
    if qty <= 0:
        raise ValueError(f"QTY_ZERO symbol={symbol} price={price}")

    order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
    order = client.futures_create_order(
        symbol=symbol,
        side=order_side,
        type=ORDER_TYPE_MARKET,
        quantity=float(qty),
        positionSide=side,
    )
    print(
        f"OPENED symbol={symbol} side={side} margin_usdt={margin_usdt:.4f} "
        f"qty={qty} order_id={order.get('orderId')}"
    )
    return order


def find_liquid_symbol(client, step_sizes: dict, exclude: set, side: str) -> Optional[str]:
    try:
        tickers = client.futures_ticker()
        ranked = sorted(
            [
                t
                for t in tickers
                if t["symbol"].endswith("USDT")
                and t["symbol"] in step_sizes
                and t["symbol"] not in exclude
            ],
            key=lambda x: float(x.get("quoteVolume", 0)),
            reverse=True,
        )
        for t in ranked[:50]:
            sym = t["symbol"]
            try:
                client.futures_symbol_ticker(symbol=sym)
                return sym
            except Exception:
                continue
    except Exception as e:
        print(f"LIQUID_SEARCH_ERR={e}")
    return None


def try_open_with_backup(
    client,
    primary: str,
    backup: str,
    side: str,
    margin_usdt: float,
    step_sizes: dict,
    exclude: set,
) -> bool:
    candidates = [primary, backup]
    for sym in list(candidates):
        try:
            r = open_market(client, sym, side, margin_usdt, step_sizes, f"OPEN_{sym}_{side}")
            if r:
                exclude.add(sym)
                return True
        except Exception as e:
            err = str(e)
            print(f"FAIL symbol={sym} side={side} err={err}")
            if "-1121" in err or "SYMBOL_NOT_TRADING" in err:
                print(f"SKIP_INVALID_SYMBOL symbol={sym}")
                continue

    alt = find_liquid_symbol(client, step_sizes, exclude, side)
    if alt:
        print(f"DYNAMIC_BACKUP symbol={alt} side={side}")
        try:
            r = open_market(client, alt, side, margin_usdt, step_sizes, f"OPEN_{alt}_{side}")
            if r:
                exclude.add(alt)
                return True
        except Exception as e:
            print(f"DYNAMIC_BACKUP_FAIL symbol={alt} err={e}")
    return False


def main() -> None:
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)

    balance = account.get_usdt_balance()
    slot_size = balance / SLOT_COUNT
    margin_usdt = slot_size * ENTRY_SLOT_RATIO

    print(f"BALANCE_USDT={balance:.4f}")
    print(f"SLOT_SIZE={slot_size:.4f}")
    print(f"ENTRY_MARGIN={margin_usdt:.4f}")
    print(f"LEVERAGE={LEVERAGE}x ISOLATED")

    ensure_hedge_mode(client)
    step_sizes = get_step_sizes(client)
    exclude: set = set()

    opened = 0

    for primary, backup in LONG_PLAN:
        if try_open_with_backup(client, primary, backup, "LONG", margin_usdt, step_sizes, exclude):
            opened += 1
        time.sleep(0.3)

    for primary, backup in SHORT_PLAN:
        if try_open_with_backup(client, primary, backup, "SHORT", margin_usdt, step_sizes, exclude):
            opened += 1
        time.sleep(0.3)

    hedge_sym = HEDGE_PRIMARY if HEDGE_PRIMARY in step_sizes else None
    if not hedge_sym:
        hedge_sym = find_liquid_symbol(client, step_sizes, exclude, "LONG")
        print(f"HEDGE_FALLBACK symbol={hedge_sym}")

    if hedge_sym:
        for side in ("LONG", "SHORT"):
            try:
                r = open_market(client, hedge_sym, side, margin_usdt, step_sizes, f"HEDGE_{hedge_sym}_{side}")
                if r:
                    opened += 1
                    exclude.add(hedge_sym)
            except Exception as e:
                print(f"HEDGE_FAIL symbol={hedge_sym} side={side} err={e}")
            time.sleep(0.3)

    print(f"POSITIONS_SENT_COUNT={opened}")

    print(f"STRESS_TEST symbol={STRESS_SYMBOL} side=LONG")
    ok, reason = _slot_limit_check(client, STRESS_SYMBOL, "LONG", margin_usdt, "STRESS_BTC")
    if not ok:
        print("✅ SLOT LİMİTİ ÇALIŞTI - BTC REDDEDİLDİ")
        print(f"STRESS_REJECT_REASON={reason}")
    else:
        try:
            r = open_market(client, STRESS_SYMBOL, "LONG", margin_usdt, step_sizes, "STRESS_BTC")
            if r:
                print("❌ KRİTİK HATA - SLOT LİMİTİ ÇALIŞMADI")
            else:
                print("✅ SLOT LİMİTİ ÇALIŞTI - BTC REDDEDİLDİ")
        except Exception as e:
            print(f"STRESS_EXCEPTION={e}")

    balance_after = account.get_usdt_balance()
    all_pos = client.futures_position_information()
    open_count = sum(1 for p in all_pos if float(p.get("positionAmt", 0)) != 0)
    print(f"FINAL_BALANCE_USDT={balance_after:.4f}")
    print(f"FINAL_OPEN_POSITION_COUNT={open_count}")


if __name__ == "__main__":
    main()
