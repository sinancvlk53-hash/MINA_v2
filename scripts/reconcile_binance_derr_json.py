#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance vs DERR vs JSON tracking uyum kontrolü — ham çıktı."""
import json
import os
import sqlite3
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from config import BinanceConfig
import mina_tracking as mt

TRACKING = list(mt.TRACKING_FILES) + ["mina_position_state.json", "position_sources.json"]
MERTER = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    client = BinanceConfig().get_client()

    print("=" * 70)
    print("BINANCE TESTNET — AÇIK POZİSYONLAR (ham)")
    print("=" * 70)
    all_pos = client.futures_position_information()
    open_pos = [p for p in all_pos if float(p.get("positionAmt") or 0) != 0]
    print(f"toplam sembol tarandı: {len(all_pos)} | açık: {len(open_pos)}\n")
    for p in sorted(open_pos, key=lambda x: (x["symbol"], float(x["positionAmt"]))):
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        key = mt.pos_key(p["symbol"], side)
        print(f"--- {key} ---")
        for k in sorted(p.keys()):
            print(f"  {k}: {p[k]}")
        print()

    print("=" * 70)
    print("DERR — AÇIK KAYITLAR (ham)")
    print("=" * 70)
    conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='open' ORDER BY id"
    ).fetchall()
    print(f"açık kayıt sayısı: {len(rows)}\n")
    for r in rows:
        print(f"--- trade id={r['id']} ---")
        for k in r.keys():
            print(f"  {k}: {r[k]}")
        print()
    conn.close()

    print("=" * 70)
    print("JSON TRACKING DOSYALARI (ham)")
    print("=" * 70)
    for fn in TRACKING:
        data = mt.load_json(fn)
        print(f"\n>>> {fn}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n>>> signal_bot/merter_dca_state.json")
    with open(MERTER, encoding="utf-8") as f:
        print(f.read())

    print("=" * 70)
    print("UYUM ANALİZİ")
    print("=" * 70)

    binance_keys = set()
    for p in open_pos:
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        binance_keys.add(mt.pos_key(p["symbol"], side))

    derr_keys = set()
    conn = sqlite3.connect(os.path.join(ROOT, "mina_trading_journal.db"))
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT symbol, side FROM trades WHERE status='open'"):
        derr_keys.add(mt.pos_key(r["symbol"], r["side"]))
    conn.close()

    initial_prices = mt.load_json(mt.INITIAL_PRICE_FILE)
    initial_margins = mt.load_json(mt.INITIAL_MARGIN_FILE)
    defense_levels = mt.load_json(mt.DEFENSE_FILE)
    tp_levels = mt.load_json(mt.TP_FILE)
    max_prices = mt.load_json(mt.MAX_PRICE_FILE)
    pos_sources = mt.load_json("position_sources.json")
    pos_state = mt.load_json("mina_position_state.json")

    tracking_keys = set(initial_prices.keys())
    for d in (initial_margins, defense_levels, tp_levels, max_prices):
        tracking_keys |= set(d.keys())

    print(f"Binance keys ({len(binance_keys)}): {sorted(binance_keys)}")
    print(f"DERR keys     ({len(derr_keys)}): {sorted(derr_keys)}")
    print(f"Tracking keys ({len(tracking_keys)}): {sorted(tracking_keys)}")
    print(f"position_sources keys ({len(pos_sources)}): {sorted(pos_sources.keys())}")
    print(f"mina_position_state keys ({len(pos_state)}): {sorted(pos_state.keys())}")

    def diff(a, b, label):
        only_a = sorted(a - b)
        only_b = sorted(b - a)
        if only_a:
            print(f"  SADECE {label[0]}: {only_a}")
        if only_b:
            print(f"  SADECE {label[1]}: {only_b}")
        return not only_a and not only_b

    ok = True
    print("\n[Binance vs DERR]")
    if not diff(binance_keys, derr_keys, ("Binance", "DERR")):
        ok = False
    else:
        print("  OK — aynı key seti")

    print("\n[Binance vs Tracking (initial_entry_prices)]")
    if not diff(binance_keys, set(initial_prices.keys()), ("Binance", "initial_entry_prices")):
        ok = False
    else:
        print("  OK — aynı key seti")

    print("\n[Tracking dosyaları arası key tutarlılığı]")
    for fn, data in [
        ("initial_margins", initial_margins),
        ("defense_levels", defense_levels),
        ("tp_levels", tp_levels),
        ("max_prices", max_prices),
    ]:
        if set(data.keys()) != set(initial_prices.keys()):
            print(f"  UYUMSUZ {fn}: keys={sorted(data.keys())}")
            ok = False
        else:
            print(f"  OK {fn}")

    print("\n[position_sources vs Binance]")
    if not diff(binance_keys, set(pos_sources.keys()), ("Binance", "position_sources")):
        ok = False
    else:
        print("  OK")

    print("\n" + "=" * 70)
    if ok and binance_keys == derr_keys == tracking_keys:
        print("SONUÇ: TAM UYUMLU")
    else:
        print("SONUÇ: UYUMSUZLUK VAR — yukarıdaki farklara bak")
    print("=" * 70)


if __name__ == "__main__":
    main()
