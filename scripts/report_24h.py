#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""24 saat raporu — 2026-06-04 12:00 UTC → 2026-06-05 12:00 UTC. Ham çıktı."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

SEP = "=" * 80
MOTOR_PAT = re.compile(
    r"2026-06-04 1[2-9]|2026-06-04 2[0-9]|2026-06-05 0[0-9]|2026-06-05 1[0-2]"
)
MERTER_PAT = re.compile(
    r"2026-06-04T1[2-9]|2026-06-04T2[0-9]|2026-06-05T0[0-9]|2026-06-05T1[0-2]"
)
SIGNAL_PAT = re.compile(
    r"2026-06-04 1[2-9]|2026-06-04 2[0-9]|2026-06-05 0[0-9]|2026-06-05 1[0-2]"
)
ACTION_PAT = re.compile(
    r"TP|trailing|Trailing|savunma|defense|D1|D2|D3|hard.?stop|Hard.?Stop|"
    r"STOP|breakeven|Breakeven|execute|take_profit|KAPAT",
    re.I,
)


def section(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


def motor_log() -> None:
    section("1. mina_bot.log — TP / takip / savunma / hard stop")
    path = f"{ROOT}/mina_bot.log"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if MOTOR_PAT.search(line) and ACTION_PAT.search(line):
                print(line.rstrip())


def derr_closed() -> None:
    section("2. DERR — kapanan işlemler (close_time >= 2026-06-04 12:00)")
    db = f"{ROOT}/mina_trading_journal.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol, side, leverage, open_price, close_price, close_reason,
               pnl_usdt, open_time, close_time, signal_source
        FROM trades
        WHERE close_time >= '2026-06-04 12:00'
        ORDER BY close_time
        """
    )
    for r in cur.fetchall():
        print(dict(r))
    conn.close()


def merter_log() -> None:
    section("3. merter_dca.log — 24h aktivite")
    path = f"{ROOT}/signal_bot/merter_dca.log"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if MERTER_PAT.search(line):
                print(line.rstrip())


def signal_decisions() -> None:
    section("4. signal_decisions (created_at >= 2026-06-04 12:00, son 20 DESC)")
    db = f"{ROOT}/mina_trading_journal.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT merter_symbol, k2_label, k3_action, created_at
        FROM signal_decisions
        WHERE created_at >= '2026-06-04 12:00'
        ORDER BY created_at DESC
        LIMIT 20
        """
    )
    for r in cur.fetchall():
        print(dict(r))
    conn.close()


def haluk_signals() -> None:
    section("5. signals_log.txt — Haluk/PDF/Telegram (tail -30 filtreli)")
    path = f"{ROOT}/signal_bot/signals_log.txt"
    matched = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if SIGNAL_PAT.search(line):
                matched.append(line.rstrip())
    for ln in matched[-30:]:
        print(ln)


def open_positions_and_balance() -> None:
    section("6. Binance — açık pozisyonlar + signal_source")
    from backend.config import BinanceConfig, AccountManager

    try:
        from mina_signal_source import SOURCE_LABELS, get_position_sources
        position_sources = get_position_sources()
    except ImportError:
        SOURCE_LABELS = {"HT": "Haluk Hoca", "MZ": "Merter", "MANUEL": "Manuel"}
        position_sources = json.load(open(f"{ROOT}/position_sources.json"))

    client = BinanceConfig().get_client()
    account = AccountManager(client)
    balance = account.get_usdt_balance()
    raw = client.futures_position_information()
    open_pos = [p for p in raw if float(p["positionAmt"]) != 0]
    total_upnl = 0.0

    for p in open_pos:
        sym = p["symbol"]
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        entry = float(p["entryPrice"])
        mark = float(p.get("markPrice") or 0)
        upnl = float(p["unRealizedProfit"])
        lev = int(p["leverage"])
        iso_m = float(p.get("isolatedMargin") or 0)
        init_m = iso_m if iso_m > 0 else (abs(amt) * entry / max(lev, 1))
        roe = (upnl / init_m * 100) if init_m > 0 else 0
        pnl_pct = (
            (mark - entry) / entry * 100
            if side == "LONG" and entry
            else (entry - mark) / entry * 100 if entry else 0
        )
        pos_key = f"{sym}_{side}"
        src = position_sources.get(pos_key)
        src_label = SOURCE_LABELS.get(src, src) if src else None
        total_upnl += upnl
        print(
            f"{sym} {side} {lev}x | entry={entry} mark={mark} | "
            f"PnL={upnl} USDT ({pnl_pct:.4f}%) ROE={roe:.4f}% | "
            f"qty={abs(amt)} margin={iso_m} | signal_source={src} ({src_label})"
        )

    section("7. Kasa durumu")
    conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol, side, close_reason, pnl_usdt, close_time, signal_source
        FROM trades
        WHERE close_time >= '2026-06-04 12:00'
        ORDER BY close_time
        """
    )
    closed_rows = cur.fetchall()
    realized_today = sum(float(r["pnl_usdt"] or 0) for r in closed_rows)
    conn.close()

    print(f"balance_usdt={balance}")
    print(f"realized_pnl_since_2026-06-04_12:00={realized_today}")
    print(f"open_positions_count={len(open_pos)}")
    print(f"total_unrealized_pnl={total_upnl}")
    print(f"floating_equity_approx={balance + total_upnl}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    motor_log()
    derr_closed()
    merter_log()
    signal_decisions()
    haluk_signals()
    open_positions_and_balance()
    print(f"\n{SEP}\nRAPOR BİTTİ\n{SEP}")
