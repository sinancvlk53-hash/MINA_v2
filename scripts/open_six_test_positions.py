#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reset state, open 6 testnet positions, seed tracking + DERR."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

from config import BinanceConfig, AccountManager  # noqa: E402
from mina_position_manager import MinaPositionManager  # noqa: E402
from mina_trading_journal import TradingJournal  # noqa: E402
from mina_signal_source import MANUEL  # noqa: E402
import mina_tracking as mt  # noqa: E402
from open_fast_coins import (  # noqa: E402
    LEVERAGE,
    SLOT_COUNT,
    ensure_hedge_mode,
    get_step_sizes,
    open_market,
)

def seed_tracking(manager, symbol: str, side: str, entry_price: float, margin: float) -> None:
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


LONGS = ["SOLUSDT", "LINKUSDT", "INJUSDT"]
SHORTS = ["XRPUSDT", "ADAUSDT", "DOTUSDT"]


def reset_json(name: str) -> None:
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f)
        f.write("\n")


def read_position(client, symbol: str, side: str):
    for p in client.futures_position_information():
        if p["symbol"] != symbol:
            continue
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        ps = "LONG" if amt > 0 else "SHORT"
        if ps != side:
            continue
        return {
            "entry": float(p.get("entryPrice") or 0),
            "qty": abs(amt),
            "margin": float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0),
            "leverage": int(float(p.get("leverage") or LEVERAGE)),
            "mark": float(p.get("markPrice") or 0),
        }
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== 1) JSON sifirla ===")
    for name in ("mina_position_state.json", "position_sources.json"):
        reset_json(name)
        print(f"  OK {name} -> {{}}")

    print("\n=== 2) Motor yeniden baslat ===")
    subprocess.run(["systemctl", "restart", "mina-engine.service"], check=False)
    time.sleep(4)
    subprocess.run(["systemctl", "stop", "mina-engine.service"], check=False)
    time.sleep(2)
    print("  mina-engine durduruldu (acilis sirasinda cakisma onlemi)")

    cfg = BinanceConfig()
    client = cfg.get_client()
    account = AccountManager(client)

    balance = account.get_usdt_balance()
    slot_size = balance / SLOT_COUNT
    margin_usdt = slot_size / 5

    print("\n=== 3) Bakiye / marjin ===")
    print(f"  USDT bakiye    : {balance:.4f}")
    print(f"  Slot (kasa/10) : {slot_size:.4f}")
    print(f"  Giris (slot/5) : {margin_usdt:.4f}")
    print(f"  Hacim (4x)     : {margin_usdt * LEVERAGE:.4f}")
    print(f"  Mod            : hedge + isolated {LEVERAGE}x")

    ensure_hedge_mode(client)
    step_sizes = get_step_sizes(client)

    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    journal = TradingJournal(db_path=db_path)
    manager = MinaPositionManager(client, slot_size, journal=journal, data_root=ROOT)

    plan = [(s, "LONG") for s in LONGS] + [(s, "SHORT") for s in SHORTS]
    results = []

    print("\n=== 4) Pozisyon ac ===")
    for symbol, side in plan:
        if symbol not in step_sizes:
            print(f"  FAIL {symbol} {side}: sembol TRADING degil")
            results.append({"symbol": symbol, "side": side, "ok": False, "error": "NOT_TRADING"})
            continue
        try:
            order = open_market(client, symbol, side, margin_usdt, step_sizes, f"MANUAL_{symbol}_{side}")
            if not order:
                results.append({"symbol": symbol, "side": side, "ok": False, "error": "SLOT_LIMIT"})
                continue
            time.sleep(0.4)
            pos = read_position(client, symbol, side)
            if not pos:
                results.append({"symbol": symbol, "side": side, "ok": False, "error": "NO_POSITION_AFTER_ORDER"})
                continue

            actual_margin = pos["margin"] if pos["margin"] > 0 else margin_usdt
            seed_tracking(manager, symbol, side, pos["entry"], actual_margin)
            manager.log_position_open(
                symbol=symbol,
                side=side,
                leverage=pos["leverage"],
                entry_price=pos["entry"],
                qty=pos["qty"],
                initial_margin=actual_margin,
                signal_source=MANUEL,
            )
            trade_id = manager.trade_ids.get(manager._pos_key(symbol, side))
            row = {
                "symbol": symbol,
                "side": side,
                "ok": True,
                "entry": pos["entry"],
                "qty": pos["qty"],
                "margin": actual_margin,
                "leverage": pos["leverage"],
                "order_id": order.get("orderId"),
                "trade_id": trade_id,
            }
            results.append(row)
            print(
                f"  OK {symbol} {side} entry={pos['entry']} qty={pos['qty']} "
                f"margin={actual_margin:.4f} derr_id={trade_id}"
            )
        except Exception as e:
            print(f"  FAIL {symbol} {side}: {e}")
            results.append({"symbol": symbol, "side": side, "ok": False, "error": str(e)})
        time.sleep(0.3)

    print("\n=== 5) Motor baslat ===")
    subprocess.run(["systemctl", "start", "mina-engine.service"], check=False)
    time.sleep(3)

    balance_after = account.get_usdt_balance()
    open_pos = [
        p for p in client.futures_position_information()
        if float(p.get("positionAmt") or 0) != 0
    ]

    print("\n=== 6) DERR acik kayitlar ===")
    cursor = journal.conn.cursor()
    cursor.execute(
        "SELECT id, symbol, side, leverage, open_price, open_qty, initial_margin, signal_source "
        "FROM trades WHERE status='open' ORDER BY id"
    )
    derr_rows = cursor.fetchall()
    for r in derr_rows:
        print(
            f"  id={r['id']} {r['symbol']} {r['side']} {r['leverage']}x "
            f"entry={r['open_price']} qty={r['open_qty']} margin={r['initial_margin']} src={r['signal_source']}"
        )

    ok_count = sum(1 for r in results if r.get("ok"))
    print("\n=== OZET ===")
    print(f"  Acilan         : {ok_count}/6")
    print(f"  Binance acik   : {len(open_pos)}")
    print(f"  DERR acik      : {len(derr_rows)}")
    print(f"  Bakiye once    : {balance:.4f} USDT")
    print(f"  Bakiye sonra   : {balance_after:.4f} USDT")
    print(f"  Kullanilan marj  : ~{balance - balance_after:.4f} USDT")

    journal.close()


if __name__ == "__main__":
    main()
