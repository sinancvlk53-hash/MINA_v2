#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MOVRUSDT, ALGOUSDT, BTCUSDT SHORT detay raporu + BTC LONG savunma."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)

SYMS = ["MOVRUSDT", "ALGOUSDT", "BTCUSDT"]
DB = f"{ROOT}/mina_trading_journal.db"
LOG = f"{ROOT}/mina_bot.log"
MER = f"{ROOT}/signal_bot/merter_dca.log"


def parse_dict(s: str) -> dict:
    m = re.search(r"\{.*\}", s)
    if not m:
        return {}
    try:
        return eval(m.group())
    except Exception:
        return {}


def derr_rows(sym: str, side: Optional[str] = None) -> List[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if side:
        q = "SELECT * FROM trades WHERE symbol=? AND side=? ORDER BY id"
        rows = con.execute(q, (sym, side)).fetchall()
    else:
        rows = con.execute("SELECT * FROM trades WHERE symbol=? ORDER BY id", (sym,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def log_events(sym: str) -> List[dict]:
    out = []
    try:
        lines = open(LOG, encoding="utf-8", errors="replace").readlines()
    except FileNotFoundError:
        return out
    for line in lines:
        if sym not in line:
            continue
        ts_m = re.match(r"\[([^\]]+)\]", line)
        ts = ts_m.group(1) if ts_m else ""
        d = parse_dict(line)
        act = (d.get("action") or "").lower()
        if act in ("take_profit", "trailing_stop", "stop_loss", "defense", "open", "close"):
            out.append({"ts": ts, "action": act, "data": d, "raw": line.rstrip()})
        elif "defense" in line.lower() or "trailing" in line.lower() or "stop_loss" in line.lower():
            out.append({"ts": ts, "action": act or "info", "data": d, "raw": line.rstrip()})
    return out


def user_trades(sym: str) -> List[dict]:
    from backend.config import BinanceConfig
    client = BinanceConfig().get_client()
    trades = client.futures_account_trades(symbol=sym, limit=500)
    return trades


def fmt(v, n=6):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{n}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def report_coin(sym: str, side_filter: Optional[str] = None):
    print("=" * 80)
    print(f"  {sym}" + (f" ({side_filter})" if side_filter else ""))
    print("=" * 80)

    trades = derr_rows(sym, side_filter)
    print("\n--- DERR trades (ham) ---")
    if not trades:
        print("(kayıt yok)")
    for t in trades:
        print(json.dumps({k: t[k] for k in t.keys()}, default=str, ensure_ascii=False))

    ref = None
    if side_filter:
        closed = [t for t in trades if t["status"] == "closed" and t["side"] == side_filter]
        ref = closed[-1] if closed else None
    else:
        closed = [t for t in trades if t["status"] == "closed"]
        ref = closed[-1] if closed else None

    print("\n--- Özet (son kapanan DERR) ---")
    if ref:
        open_usdt = float(ref.get("open_notional") or ref["open_price"] * ref["open_qty"])
        close_usdt = float(ref.get("close_price") or 0) * float(ref.get("close_qty") or 0)
        print(f"  trade_id          : {ref['id']}")
        print(f"  side / leverage   : {ref['side']} / {ref['leverage']}x")
        print(f"  signal_source     : {ref.get('signal_source')}")
        print(f"  açılış zamanı     : {ref['open_time']}")
        print(f"  açılış fiyat      : {fmt(ref['open_price'])}")
        print(f"  açılış qty        : {fmt(ref['open_qty'], 4)}")
        print(f"  açılış USDT       : {fmt(open_usdt, 4)}")
        print(f"  initial_margin    : {fmt(ref.get('initial_margin'), 4)}")
        print(f"  kapanış zamanı    : {ref.get('close_time')}")
        print(f"  kapanış fiyat     : {fmt(ref.get('close_price'))}")
        print(f"  kapanış qty       : {fmt(ref.get('close_qty'), 4)}")
        print(f"  kapanış USDT      : {fmt(close_usdt, 4)}")
        print(f"  close_reason      : {ref.get('close_reason')}")
        print(f"  pnl_usdt          : {fmt(ref.get('pnl_usdt'), 4)}")
        print(f"  pnl_percent       : {fmt(ref.get('pnl_percent'), 2)}%")
        print(f"  defense_triggered : {ref.get('defense_triggered')}")
    else:
        print("  (kapanan DERR kaydı yok)")

    events = log_events(sym)
    if side_filter:
        # BTC için SHORT olayları — log side içermiyor, sembol yeterli
        pass
    print("\n--- mina_bot.log olayları (ham) ---")
    for e in events:
        print(e["raw"])

    tp1 = [e for e in events if e["action"] == "take_profit" and e["data"].get("level") == 1]
    tp2 = [e for e in events if e["action"] == "take_profit" and e["data"].get("level") == 2]
    trail = [e for e in events if e["action"] == "trailing_stop"]
    stops = [e for e in events if e["action"] == "stop_loss"]

    print("\n--- TP / Trailing / Stop özeti ---")
    if tp1:
        e = tp1[-1]
        print(f"  TP1 zaman : {e['ts']}")
        print(f"  TP1 ham   : {e['raw']}")
    else:
        print("  TP1 : —")
    if tp2:
        e = tp2[-1]
        print(f"  TP2 zaman : {e['ts']}")
        print(f"  TP2 ham   : {e['raw']}")
    else:
        print("  TP2 : —")
    if trail:
        e = trail[-1]
        print(f"  Trailing zaman : {e['ts']}")
        print(f"  Trailing ham   : {e['raw']}")
    else:
        print("  Trailing : —")
    if stops:
        e = stops[-1]
        print(f"  Stop zaman : {e['ts']}")
        print(f"  Stop ham   : {e['raw']}")

    print("\n--- Binance userTrades (ham, son 500) ---")
    try:
        ut = user_trades(sym)
        if ref and ref.get("open_time"):
            ot = str(ref["open_time"])[:19]
            ct = str(ref.get("close_time") or "")[:19]
            filtered = []
            for t in ut:
                ts = datetime.fromtimestamp(t["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                if ot <= ts.replace("T", " ")[:19] or (ct and ts.replace("T", " ")[:19] <= ct):
                    if not ref.get("close_time") or ts.replace("T", " ")[:19] <= ct:
                        filtered.append(t)
            if filtered:
                ut = filtered
        for t in reversed(ut[-40:]):
            ts = datetime.fromtimestamp(t["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  {ts} {t['side']:4} qty={t['qty']:>12} price={t['price']:>14} "
                f"realizedPnl={t.get('realizedPnl', 0):>12} commission={t.get('commission', 0)} id={t['id']}"
            )
        total_realized = sum(float(t.get("realizedPnl") or 0) for t in ut)
        total_comm = sum(float(t.get("commission") or 0) for t in ut)
        print(f"\n  userTrades toplam realizedPnl : {total_realized:.6f} USDT")
        print(f"  userTrades toplam commission  : {total_comm:.6f} USDT")
        print(f"  net (realized - commission)   : {total_realized - total_comm:.6f} USDT")
    except Exception as ex:
        print(f"  HATA: {ex}")

    if sym == "MOVRUSDT":
        print("\n--- merter_dca.log (MOVR) ---")
        try:
            for l in open(MER, encoding="utf-8", errors="replace"):
                if "MOVR" in l.upper():
                    print(l.rstrip())
        except FileNotFoundError:
            print("(yok)")


def report_btc_long_defense():
    print("\n" + "=" * 80)
    print("  BTCUSDT LONG — SAVUNMA DURUMU")
    print("=" * 80)

    for fn in ["defense_levels.json", "initial_margins.json", "initial_prices.json", "tp_levels.json"]:
        p = f"{ROOT}/{fn}"
        try:
            d = json.load(open(p))
            btc = {k: v for k, v in d.items() if "BTC" in k and "LONG" in k}
            if btc:
                print(f"\n--- {fn} ---")
                print(json.dumps(btc, indent=2))
        except FileNotFoundError:
            print(f"\n--- {fn} --- (dosya yok)")
        except Exception as e:
            print(f"\n--- {fn} --- HATA: {e}")

    print("\n--- DERR açık BTC LONG ---")
    for t in derr_rows("BTCUSDT", "LONG"):
        if t["status"] == "open":
            print(json.dumps(t, default=str, ensure_ascii=False))

    print("\n--- mina_bot.log BTCUSDT defense (ham) ---")
    try:
        for line in open(LOG, encoding="utf-8", errors="replace"):
            if "BTCUSDT" not in line:
                continue
            if any(x in line.lower() for x in ("defense", "d1", "d2", "d3", "savunma", "hard stop")):
                print(line.rstrip())
    except FileNotFoundError:
        pass

    print("\n--- Binance BTCUSDT LONG pozisyon ---")
    try:
        from backend.config import BinanceConfig
        client = BinanceConfig().get_client()
        for p in client.futures_position_information(symbol="BTCUSDT"):
            amt = float(p["positionAmt"])
            if amt == 0:
                continue
            ps = p.get("positionSide", "BOTH")
            if ps in ("LONG", "BOTH") and amt > 0:
                print(json.dumps({
                    k: p[k] for k in (
                        "symbol", "positionAmt", "entryPrice", "markPrice",
                        "leverage", "isolatedMargin", "unRealizedProfit", "positionSide"
                    )
                }, indent=2))
                entry = float(p["entryPrice"])
                mark = float(p["markPrice"])
                lev = int(p["leverage"])
                margin = float(p["isolatedMargin"])
                upnl = float(p["unRealizedProfit"])
                roe = (upnl / margin * 100) if margin else 0
                d1 = entry * 0.95
                print(f"  D1 tetik fiyatı (entry×0.95) : {d1:.2f}")
                print(f"  mark vs D1                   : mark={mark:.2f} {'<= D1 (TETİKLENDİ)' if mark <= d1 else '> D1 (henüz değil)'}")
                print(f"  ROE (unRealized/margin)      : {roe:.2f}%")
    except Exception as ex:
        print(f"  HATA: {ex}")


def main():
    report_coin("MOVRUSDT")
    report_coin("ALGOUSDT")
    report_coin("BTCUSDT", "SHORT")
    report_btc_long_defense()


if __name__ == "__main__":
    main()
