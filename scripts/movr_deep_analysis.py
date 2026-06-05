#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MOVRUSDT detaylı analiz + state restore hazırlık."""
import json
import os
import sqlite3
import subprocess
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)

TP1_PCT = 0.03
TP2_PCT = 0.05


def sep(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def movr_log():
    sep("merter_dca.log — TÜM MOVR")
    p = subprocess.run(
        ["grep", "-i", "MOVR", f"{ROOT}/signal_bot/merter_dca.log"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print(p.stdout or "(yok)")


def binance_movr():
    sep("Binance MOVRUSDT")
    from backend.config import BinanceConfig
    client = BinanceConfig().get_client()
    pos = None
    for p in client.futures_position_information(symbol="MOVRUSDT"):
        amt = float(p["positionAmt"])
        if amt != 0:
            pos = p
            break
    if not pos:
        print("Pozisyon yok")
        return None
    entry = float(pos["entryPrice"])
    mark = float(pos.get("markPrice") or 0)
    qty = abs(float(pos["positionAmt"]))
    print(f"qty={qty} entry={entry} mark={mark} lev={pos['leverage']} upnl={pos['unRealizedProfit']}")
    tp1 = entry * (1 + TP1_PCT)
    tp2 = entry * (1 + TP2_PCT)
    print(f"TP1 eşiği (avg*1.03)={tp1:.6f} mark>=tp1? {mark >= tp1}")
    print(f"TP2 eşiği (avg*1.05)={tp2:.6f} mark>=tp2? {mark >= tp2}")

    # open orders
    print("\nAçık emirler:")
    for o in client.futures_get_open_orders(symbol="MOVRUSDT"):
        print(f"  {o.get('orderId')} {o.get('type')} {o.get('side')} price={o.get('price')} qty={o.get('origQty')} status={o.get('status')}")

    # trade history since open
    print("\nSon işlemler (userTrades):")
    trades = client.futures_account_trades(symbol="MOVRUSDT", limit=50)
    for t in trades[-20:]:
        print(
            f"  {t.get('time')} id={t.get('id')} side={t.get('side')} "
            f"qty={t.get('qty')} price={t.get('price')} realized={t.get('realizedPnl')}"
        )
    return {"qty": qty, "entry": entry, "mark": mark}


def motor_tp():
    sep("mina_bot.log MOVR TP/motor")
    p = subprocess.run(
        ["grep", "-i", "MOVR", f"{ROOT}/mina_bot.log"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for ln in p.stdout.splitlines():
        if any(x in ln.upper() for x in ("TP", "TAKE", "CLOSE", "EXECUTE", "HAYALET", "SELL", "KAPAT")):
            print(ln)

    sep("journal + tracking MOVR")
    conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT * FROM trades WHERE symbol='MOVRUSDT'").fetchall():
        print(dict(r))
    conn.close()

    for fname in ("initial_margins.json", "tp_levels.json", "initial_prices.json"):
        path = f"{ROOT}/{fname}"
        if os.path.isfile(path):
            data = json.load(open(path))
            for k, v in data.items():
                if "MOVR" in k:
                    print(f"{fname} {k}={v}")


def state_file():
    sep("merter_dca_state.json")
    path = f"{ROOT}/signal_bot/merter_dca_state.json"
    if os.path.isfile(path):
        print(open(path, encoding="utf-8").read())
    else:
        print("yok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    movr_log()
    binance_movr()
    motor_tp()
    state_file()
