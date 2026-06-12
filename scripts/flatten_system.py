#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance flat + JSON state sıfırla + journal open kayıtları kapat."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import BinanceConfig, AccountManager

RESET_JSON = [
    "position_states.json",
    "initial_entry_prices.json",
    "defense_levels.json",
    "tp_levels.json",
    "max_prices.json",
    "stop_levels.json",
    "pending_orders.json",
    "defense_stop_orders.json",
    "initial_margins.json",
    "position_sources.json",
    "initial_prices.json",
]

DB_PATH = os.path.join(ROOT, "mina_trading_journal.db")
MERter_STATE = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def cancel_all_orders(client) -> int:
    symbols: set[str] = set()
    try:
        for o in client.futures_get_open_orders():
            symbols.add(o["symbol"])
    except Exception as exc:
        print(f"open orders list hata: {exc}")
    try:
        for p in client.futures_position_information():
            if float(p.get("positionAmt") or 0) != 0:
                symbols.add(p["symbol"])
    except Exception as exc:
        print(f"position list hata: {exc}")

    cancelled = 0
    for sym in sorted(symbols):
        try:
            client.futures_cancel_all_open_orders(symbol=sym)
            cancelled += 1
            print(f"  emirler iptal: {sym}")
        except Exception as exc:
            print(f"  emir iptal hata {sym}: {exc}")
    return cancelled


def close_all_positions(client) -> None:
    for attempt in range(3):
        open_pos = [
            p for p in client.futures_position_information()
            if float(p.get("positionAmt") or 0) != 0
        ]
        if not open_pos:
            break
        print(f"\nKapatma turu {attempt + 1}: {len(open_pos)} pozisyon")
        for p in open_pos:
            sym = p["symbol"]
            amt = float(p["positionAmt"])
            side = "LONG" if amt > 0 else "SHORT"
            close_side = "SELL" if amt > 0 else "BUY"
            qty = abs(amt)
            try:
                order = client.futures_create_order(
                    symbol=sym,
                    side=close_side,
                    type="MARKET",
                    quantity=qty,
                    positionSide=side,
                )
                print(
                    f"  OK {sym} {side} qty={qty} "
                    f"orderId={order.get('orderId')} status={order.get('status')}"
                )
            except Exception as exc:
                print(f"  ERR {sym} {side} qty={qty}: {exc}")
        time.sleep(2)


def reset_json_files() -> None:
    for fn in RESET_JSON:
        path = os.path.join(ROOT, fn)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  OK {fn} -> {{}}")

    merter_empty = {"positions": {}, "pending_confirm": {}}
    with open(MERter_STATE, "w", encoding="utf-8") as f:
        json.dump(merter_empty, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  OK signal_bot/merter_dca_state.json -> sıfır")


def close_db_records() -> None:
    conn = sqlite3.connect(DB_PATH)
    ts = _now()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE trades
        SET status='closed',
            close_time=?,
            close_reason='manual_flatten',
            close_qty=open_qty
        WHERE status='open'
        """,
        (ts,),
    )
    trades_n = cur.rowcount

    cur.execute(
        """
        UPDATE follower_trades
        SET status='closed',
            close_time=?
        WHERE status='open'
        """,
        (ts,),
    )
    follower_n = cur.rowcount

    cur.execute(
        """
        UPDATE ht_pdf_basari_orani
        SET status='cancelled',
            close_time=?,
            result=COALESCE(result, 'manual_flatten')
        WHERE status NOT IN ('cancelled', 'closed')
        """,
        (ts,),
    )
    ht_pdf_n = cur.rowcount

    conn.commit()
    conn.close()
    print(f"  trades closed: {trades_n}")
    print(f"  follower_trades closed: {follower_n}")
    print(f"  ht_pdf_basari_orani cancelled: {ht_pdf_n}")


def verify(client) -> bool:
    open_pos = [
        p for p in client.futures_position_information()
        if float(p.get("positionAmt") or 0) != 0
    ]
    open_orders = client.futures_get_open_orders()
    print(f"\n=== DOGRULAMA ===")
    print(f"Açık pozisyon: {len(open_pos)}")
    for p in open_pos:
        print(f"  {p['symbol']} amt={p['positionAmt']} side={p.get('positionSide')}")
    print(f"Bekleyen emir: {len(open_orders)}")
    for o in open_orders[:20]:
        print(f"  {o['symbol']} {o['side']} {o['type']} @ {o.get('price')}")
    return len(open_pos) == 0 and len(open_orders) == 0


def main() -> int:
    print("=" * 60)
    print("FLATTEN SYSTEM — tam temizlik")
    print("=" * 60)

    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    print(f"Testnet={config.testnet} balance={account.get_usdt_balance():.2f} USDT\n")

    print("1) Açık emirleri iptal...")
    cancel_all_orders(client)

    print("\n2) Pozisyonları MARKET ile kapat...")
    close_all_positions(client)

    print("\n3) JSON state sıfırla...")
    reset_json_files()

    print("\n4) Veritabanı kayıtları kapat...")
    close_db_records()

    ok = verify(client)
    print("\n" + ("✅ SISTEM FLAT — Binance temiz" if ok else "⚠️ Hâlâ açık pozisyon/emir var"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
