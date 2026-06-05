#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabah kontrol — pozisyonlar, DERR kapanan, Merter DCA."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
if os.path.isdir(os.path.join(os.path.dirname(__file__), "..")):
    _local = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isfile(os.path.join(_local, ".env")):
        ROOT = _local

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from config import BinanceConfig, AccountManager


def list_open_positions():
    print("=" * 72)
    print("BINANCE TESTNET — AÇIK POZİSYONLAR")
    print("=" * 72)
    cfg = BinanceConfig()
    client = cfg.get_client()
    print(f"Mod: {'TESTNET' if cfg.testnet else 'MAINNET'}\n")

    positions = client.futures_position_information()
    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

    if not open_pos:
        print("(açık pozisyon yok)\n")
        return

    hdr = f"{'Sembol':<14} {'Yön':<6} {'Giriş':>12} {'Mark':>12} {'PnL USDT':>12} {'ROE %':>8}"
    print(hdr)
    print("-" * len(hdr))

    total_pnl = 0.0
    for p in sorted(open_pos, key=lambda x: x["symbol"]):
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        entry = float(p.get("entryPrice") or 0)
        mark = float(p.get("markPrice") or 0)
        pnl = float(p.get("unRealizedProfit") or 0)
        lev = max(float(p.get("leverage") or 1), 1)
        margin = float(p.get("isolatedMargin") or p.get("initialMargin") or 0)
        if margin <= 0:
            margin = abs(amt * entry) / lev
        roe = (pnl / margin * 100) if margin > 0 else 0.0
        total_pnl += pnl
        print(
            f"{p['symbol']:<14} {side:<6} {entry:>12.6f} {mark:>12.6f} "
            f"{pnl:>+12.4f} {roe:>+7.2f}"
        )
    print("-" * len(hdr))
    print(f"Toplam: {len(open_pos)} pozisyon | Unrealized PnL: {total_pnl:+.4f} USDT\n")


def derr_closed_since_yesterday():
    print("=" * 72)
    print("DERR — DÜN GECE KAPANAN İŞLEMLER")
    print("=" * 72)
    db = os.path.join(ROOT, "mina_trading_journal.db")
    if not os.path.isfile(db):
        print(f"(DB yok: {db})\n")
        return

    # Dün 00:00 UTC (bugün 4 Haziran 2026 varsayımı — son 24 saat de göster)
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT symbol, side, leverage, close_reason, pnl_usdt, pnl_percent,
               open_time, close_time, signal_source
        FROM trades
        WHERE status = 'closed'
          AND close_time >= ?
        ORDER BY close_time DESC
        """,
        (since,),
    )
    rows = cur.fetchall()
    conn.close()

    print(f"Filtre: son 24 saat (close_time >= {since} UTC)\n")

    if not rows:
        print("(kapanan işlem yok)\n")
        return

    print(
        f"{'Sembol':<12} {'Yön':<6} {'Lev':>4} {'Kaynak':<12} {'Kapanış':<18} "
        f"{'PnL USDT':>10} {'Neden':<16}"
    )
    print("-" * 90)
    has_src = "signal_source" in rows[0].keys() if rows else False
    for r in rows:
        src = (r["signal_source"] or "—") if has_src else "—"
        pnl = r["pnl_usdt"]
        pnl_s = f"{pnl:+.4f}" if pnl is not None else "N/A"
        print(
            f"{r['symbol']:<12} {r['side']:<6} {r['leverage']:>4} {str(src):<12} "
            f"{(r['close_time'] or '')[:19]:<18} {pnl_s:>10} {(r['close_reason'] or ''):<16}"
        )
    print(f"\nToplam: {len(rows)} kapanan işlem\n")


def merter_dca_check():
    print("=" * 72)
    print("MERTER 1x DCA — GECE DURUMU")
    print("=" * 72)

    state_path = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
    log_path = os.path.join(ROOT, "signal_bot", "merter_dca.log")

    print("\n--- merter_dca_state.json ---")
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        positions = state.get("positions") or {}
        pending = state.get("pending_confirm") or {}
        if positions:
            print(f"\n→ AKTİF MERTER POZİSYON: {len(positions)} yuva dolu")
            for yuva, pos in positions.items():
                print(f"   {yuva}: {pos.get('symbol')} parts={pos.get('parts_filled')}/{pos.get('parts_total')}")
        else:
            print("\n→ Gece Merter pozisyonu AÇILMADI (positions boş)")
        if pending:
            print(f"→ Bekleyen çift teyit: {pending}")
    else:
        print("(dosya yok)")

    print("\n--- merter_dca.log (son 20 satır) ---")
    if os.path.isfile(log_path):
        lines = open(log_path, encoding="utf-8", errors="replace").read().splitlines()
        for line in lines[-20:]:
            print(line)
        if not lines:
            print("(boş)")
    else:
        print("(dosya yok)")

    db = os.path.join(ROOT, "mina_trading_journal.db")
    if os.path.isfile(db):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(trades)")
        cols = {r[1] for r in cur.fetchall()}
        if "signal_source" in cols:
            since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                """
                SELECT id, symbol, side, status, signal_source, created_at, close_time, pnl_usdt
                FROM trades
                WHERE signal_source IN ('merter_ei', 'merter_rsi')
                  AND (created_at >= ? OR close_time >= ?)
                ORDER BY id DESC
                """,
                (since, since),
            )
            merter_rows = cur.fetchall()
            print(f"\n--- DERR Merter (son 24s, created/close >= {since}) ---")
            if merter_rows:
                for r in merter_rows:
                    print(dict(r))
            else:
                print("(son 24 saatte Merter trade açılıp/kapanmadı)")
        conn.close()
    print()


def main():
    list_open_positions()
    derr_closed_since_yesterday()
    merter_dca_check()


if __name__ == "__main__":
    main()
