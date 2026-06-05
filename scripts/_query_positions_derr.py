#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testnet açık pozisyonlar + DERR bugün kapanan işlemler."""
from __future__ import annotations

import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from config import BinanceConfig


def list_open_positions() -> None:
    cfg = BinanceConfig()
    client = cfg.get_client()
    testnet = cfg.testnet
    print("=" * 90)
    print(f"BINANCE {'TESTNET' if testnet else 'MAINNET'} — AÇIK POZİSYONLAR")
    print("=" * 90)

    positions = client.futures_position_information()
    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

    if not open_pos:
        print("(açık pozisyon yok)")
        print()
        return

    hdr = f"{'Sembol':<16} {'Yön':<6} {'Giriş':>12} {'Mark':>12} {'PnL (USDT)':>12} {'ROE %':>8}"
    print(hdr)
    print("-" * len(hdr))

    for p in open_pos:
        sym = p["symbol"]
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        entry = float(p.get("entryPrice") or 0)
        mark = float(p.get("markPrice") or 0)
        pnl = float(p.get("unRealizedProfit") or 0)
        margin = float(p.get("isolatedMargin") or p.get("initialMargin") or 0)
        if margin <= 0:
            margin = abs(amt * entry) / max(float(p.get("leverage") or 1), 1)
        roe = (pnl / margin * 100) if margin > 0 else 0.0
        print(
            f"{sym:<16} {side:<6} {entry:>12.6f} {mark:>12.6f} "
            f"{pnl:>+12.4f} {roe:>+7.2f}"
        )
    print()


def query_derr(db_path: str) -> None:
    print("=" * 90)
    print(f"DERR — BUGÜN KAPANAN İŞLEMLER ({db_path})")
    print("=" * 90)
    if not os.path.isfile(db_path):
        print(f"(veritabanı bulunamadı: {db_path})")
        return

    sql = """
        SELECT symbol, side, close_reason, pnl_usdt, close_time
        FROM trades
        WHERE status='closed' AND date(created_at)='2026-06-03'
        ORDER BY close_time DESC
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("(kayıt yok)")
        print()
        return

    hdr = f"{'Sembol':<16} {'Yön':<6} {'Kapanış Nedeni':<22} {'PnL USDT':>10} {'close_time':<22}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        pnl = r["pnl_usdt"]
        pnl_s = f"{pnl:+.4f}" if pnl is not None else "N/A"
        print(
            f"{r['symbol']:<16} {r['side']:<6} {(r['close_reason'] or ''):<22} "
            f"{pnl_s:>10} {(r['close_time'] or ''):<22}"
        )
    print(f"\nToplam: {len(rows)} işlem")


def main() -> None:
    list_open_positions()
    local_db = os.path.join(_ROOT, "mina_trading_journal.db")
    query_derr(local_db)


if __name__ == "__main__":
    main()
