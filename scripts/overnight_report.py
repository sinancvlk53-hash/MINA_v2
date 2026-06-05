#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gece raporu — 2026-06-04 22:00 UTC – 2026-06-05 10:00 UTC."""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SEP = "=" * 72


def section(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


def grep_mina_bot() -> None:
    section("1. mina_bot.log — TP / takip / savunma / hard stop (gece)")
    pat = r"2026-06-04 2[2-9]|2026-06-05 0[0-9]|2026-06-05 10"
    action_pat = re.compile(
        r"TP|trailing|Trailing|savunma|defense|D1|D2|D3|hard.?stop|Hard.?Stop|"
        r"STOP|breakeven|Breakeven|execute|⚡|KAPAT|close",
        re.I,
    )
    log_path = os.path.join(ROOT, "mina_bot.log")
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"Dosya okunamadı: {e}")
        return

    time_re = re.compile(pat)
    matched = []
    for line in lines:
        if not time_re.search(line):
            continue
        if action_pat.search(line):
            matched.append(line.rstrip())

    if matched:
        for ln in matched:
            print(ln)
    else:
        print("(Eşleşen TP/savunma/hard stop satırı yok)")
    print(f"\n--- Toplam: {len(matched)} satır ---")


def query_trades() -> None:
    section("2. DERR — gece kapanan işlemler (close_time >= 2026-06-04 22:00)")
    db = os.path.join(ROOT, "mina_trading_journal.db")
    if not os.path.isfile(db):
        print("DB bulunamadı")
        return
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol, side, open_price, close_price, close_reason, pnl_usdt,
               open_time, close_time
        FROM trades
        WHERE close_time >= '2026-06-04 22:00'
        ORDER BY close_time
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("(Gece kapanan işlem yok)")
    else:
        for r in rows:
            print(
                f"{r['close_time']} | {r['symbol']} {r['side']} | "
                f"open={r['open_price']} close={r['close_price']} | "
                f"reason={r['close_reason']} pnl={r['pnl_usdt']} USDT | "
                f"opened={r['open_time']}"
            )
    print(f"\n--- Toplam: {len(rows)} kapanış ---")
    conn.close()


def merter_dca_log() -> None:
    section("3. Merter DCA log — gece (son 30 satır)")
    log_path = os.path.join(ROOT, "signal_bot", "merter_dca.log")
    if not os.path.isfile(log_path):
        print("merter_dca.log bulunamadı")
        return
    pat = re.compile(r"2026-06-04T2|2026-06-05T")
    with open(log_path, encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip() for ln in f if pat.search(ln)]
    tail = lines[-30:]
    if tail:
        for ln in tail:
            print(ln)
    else:
        print("(Gece Merter DCA satırı yok)")
    print(f"\n--- Gece toplam: {len(lines)} satır, gösterilen: {len(tail)} ---")


def query_signal_decisions() -> None:
    section("4. Sinyal kararları — gece (signal_decisions)")
    db = os.path.join(ROOT, "mina_trading_journal.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT merter_symbol, k2_label, k3_action, created_at
            FROM signal_decisions
            WHERE created_at >= '2026-06-04 22:00'
            ORDER BY created_at
            """
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Sorgu hatası: {e}")
        conn.close()
        return
    if not rows:
        print("(Gece sinyal kararı yok)")
    else:
        for r in rows:
            print(
                f"{r['created_at']} | {r['merter_symbol']} | "
                f"k2={r['k2_label']} k3={r['k3_action']}"
            )
    print(f"\n--- Toplam: {len(rows)} karar ---")
    conn.close()


def open_positions() -> None:
    section("5. Şu an açık pozisyonlar (Binance)")
    try:
        from backend.config import BinanceConfig, AccountManager

        client = BinanceConfig().get_client()
        account = AccountManager(client)
        raw = client.futures_position_information()
        open_pos = [p for p in raw if float(p["positionAmt"]) != 0]
        if not open_pos:
            print("(Açık pozisyon yok)")
            return
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
            print(
                f"{sym} {side} {lev}x | entry={entry:.6f} mark={mark:.6f} | "
                f"PnL={upnl:+.2f} USDT ({pnl_pct:+.2f}%) ROE={roe:+.2f}% | "
                f"qty={abs(amt)} margin={iso_m:.2f}"
            )
        bal = account.get_usdt_balance()
        print(f"\n--- Kasa: {bal:.2f} USDT | Açık: {len(open_pos)} pozisyon ---")
    except Exception as e:
        print(f"Binance hatası: {e}")


def haluk_signals_overnight() -> None:
    section("6. Haluk PDF / Telegram — gece sinyalleri (signals_log.txt)")
    candidates = [
        os.path.join(ROOT, "signal_bot", "signals_log.txt"),
        os.path.join(ROOT, "signals_log.txt"),
        os.path.join(ROOT, "signal_log.txt"),
    ]
    log_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not log_path:
        print("signals_log.txt bulunamadı")
        return
    print(f"Dosya: {log_path}\n")
    pat_time = re.compile(
        r"2026-06-04 (2[2-9]:|[23][0-9]:)|2026-06-05 (0[0-9]:|10:)"
    )
    haluk_pat = re.compile(r"HALUK|haluk|PDF|pdf|HT|telegram|TELEGRAM", re.I)
    with open(log_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    matched = []
    for ln in lines:
        if pat_time.search(ln) and haluk_pat.search(ln):
            matched.append(ln.rstrip())
    if matched:
        for ln in matched:
            print(ln)
    else:
        # broader: any overnight line with HALUK
        for ln in lines:
            if ("2026-06-04" in ln or "2026-06-05" in ln) and haluk_pat.search(ln):
                if "22:" in ln or "23:" in ln or re.search(r"2026-06-05 0[0-9]:", ln) or "2026-06-05 10:" in ln:
                    matched.append(ln.rstrip())
        if matched:
            for ln in matched:
                print(ln)
        else:
            print("(Gece Haluk/PDF/Telegram satırı yok)")
    print(f"\n--- Toplam: {len(matched)} satır ---")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    grep_mina_bot()
    query_trades()
    merter_dca_log()
    query_signal_decisions()
    open_positions()
    haluk_signals_overnight()
    print(f"\n{SEP}\nRAPOR TAMAMLANDI\n{SEP}")
