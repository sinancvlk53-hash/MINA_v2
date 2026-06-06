#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Coin bazlı detay rapor — log + DERR."""
import os
import re
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
SYMS = ["PARTIUSDT", "DOTUSDT", "ADAUSDT", "XRPUSDT", "ZROUSDT"]

REMOTE_PY = "/root/MINA_v2/scripts/_coin_detail_report.py"

LOCAL = r'''#!/usr/bin/env python3
import json
import re
import sqlite3
from datetime import datetime

SYMS = ["PARTIUSDT", "DOTUSDT", "ADAUSDT", "XRPUSDT", "ZROUSDT"]
LOG = "/root/MINA_v2/mina_bot.log"
MERter_LOG = "/root/MINA_v2/signal_bot/merter_dca.log"
DB = "/root/MINA_v2/mina_trading_journal.db"

def read_log(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except FileNotFoundError:
        return []

def parse_dict(s):
    m = re.search(r"\{.*\}", s)
    if not m:
        return {}
    try:
        return eval(m.group())  # log uses python dict repr
    except Exception:
        return {}

def lines_for_sym(lines, sym):
    return [l.rstrip() for l in lines if sym in l]

def derr_trades(sym):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT id, symbol, side, leverage, open_time, open_price, open_qty,
               close_time, close_price, close_qty, close_reason,
               pnl_usdt, pnl_percent, defense_triggered, status,
               weighted_avg_price, initial_margin, signal_source
        FROM trades WHERE symbol=? ORDER BY open_time
        """,
        (sym,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def extract_events(sym, bot_lines):
    events = []
    for line in bot_lines:
        ts_m = re.match(r"\[([^\]]+)\]", line)
        ts = ts_m.group(1) if ts_m else ""
        d = parse_dict(line)
        action = (d.get("action") or "").lower()
        reason = d.get("reason") or ""
        ev = {"ts": ts, "raw": line, "action": action, "data": d}
        if action in ("tp1", "tp2", "trailing_stop", "defense", "open", "entry", "close", "take_profit"):
            events.append(ev)
        elif "tp1" in reason.lower() or "tp2" in reason.lower():
            events.append(ev)
        elif "trailing" in reason.lower() or action == "trailing_stop":
            events.append(ev)
        elif d.get("defense_level") is not None:
            events.append(ev)
        elif "TP" in line or "Trailing" in line or "trailing" in line.lower():
            if sym in line:
                events.append(ev)
    return events

def trough_from_reason(reason):
    m = re.search(r"trough=([\d.]+)", reason or "")
    now_m = re.search(r"now=([\d.]+)", reason or "")
    return (
        float(m.group(1)) if m else None,
        float(now_m.group(1)) if now_m else None,
    )

def fmt(v, n=6):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{n}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)

def report_coin(sym):
    print("=" * 78)
    print(f"  {sym}")
    print("=" * 78)

    bot = lines_for_sym(read_log(LOG), sym)
    merter = lines_for_sym(read_log(MERter_LOG), sym) if sym == "ZROUSDT" else []
    trades = derr_trades(sym)

    # --- DERR ---
    print("\n[DERR trades]")
    if not trades:
        print("  (kayıt yok)")
    for t in trades:
        print(f"  trade_id={t['id']} status={t['status']} side={t['side']} lev={t['leverage']}x")
        print(f"    open_time={t['open_time']}  open_price={fmt(t['open_price'])}  open_qty={fmt(t['open_qty'],4)}")
        if t["status"] == "closed":
            print(f"    close_time={t['close_time']}  close_price={fmt(t['close_price'])}  close_qty={fmt(t['close_qty'],4)}")
            print(f"    close_reason={t['close_reason']}  pnl_usdt={fmt(t['pnl_usdt'],4)}  pnl_pct={fmt(t['pnl_percent'],2)}%")
        print(f"    defense_triggered={t['defense_triggered']}  signal_source={t.get('signal_source') or '—'}")

    # pick best trade for 2026-06-04 or latest closed
    active = [t for t in trades if t["status"] == "open"]
    closed = [t for t in trades if t["status"] == "closed"]
    closed_today = [t for t in closed if t.get("close_time") and str(t["close_time"]).startswith("2026-06-04")]
    ref = closed_today[-1] if closed_today else (closed[-1] if closed else (active[-1] if active else None))

    print("\n[Özet alanlar]")
    if ref:
        print(f"  Giriş fiyatı      : {fmt(ref['open_price'])}")
        print(f"  Giriş zamanı      : {ref['open_time']}")
    else:
        print("  Giriş fiyatı      : — (DERR yok)")

    events = extract_events(sym, bot)
    tp1 = [e for e in events if e["action"] == "take_profit" and e["data"].get("level") == 1]
    tp2 = [e for e in events if e["action"] == "take_profit" and e["data"].get("level") == 2]
    trail = [e for e in events if e["action"] == "trailing_stop" or "trailing" in (e["data"].get("reason") or "").lower()]

    if tp1:
        e = tp1[-1]
        d = e["data"]
        print(f"  TP1 zamanı        : {e['ts']}")
        print(f"  TP1 fiyat         : {fmt(d.get('price') or d.get('trigger_price') or d.get('fill_price'))}")
        print(f"  TP1 kapatılan qty : {fmt(d.get('qty') or d.get('close_qty') or d.get('quantity'),4)}")
    else:
        print("  TP1               : — (logda yok)")

    if tp2:
        e = tp2[-1]
        d = e["data"]
        print(f"  TP2 zamanı        : {e['ts']}")
        print(f"  TP2 fiyat         : {fmt(d.get('price') or d.get('trigger_price') or d.get('fill_price'))}")
        print(f"  TP2 kapatılan qty : {fmt(d.get('qty') or d.get('close_qty') or d.get('quantity'),4)}")
    else:
        print("  TP2               : — (logda yok)")

    if trail:
        e = trail[-1]
        d = e["data"]
        reason = d.get("reason") or ""
        trough, now_p = trough_from_reason(reason)
        print(f"  Trailing zamanı   : {e['ts']}")
        print(f"  Trailing trough   : {fmt(trough)}")
        print(f"  Trailing now/fiyat: {fmt(now_p or d.get('price'))}")
        print(f"  Trailing reason   : {reason}")
    else:
        print("  Trailing          : — (logda yok)")

    if ref and ref["status"] == "closed":
        print(f"  Net PnL (DERR)    : {fmt(ref['pnl_usdt'],4)} USDT")
    elif ref:
        print(f"  Net PnL (DERR)    : açık (henüz kapanmadı)")
    else:
        print(f"  Net PnL (DERR)    : —")

    # Merter for ZRO
    if merter:
        print("\n[merter_dca.log — ZRO]")
        for ln in merter[-15:]:
            print(f"  {ln}")

    # relevant mina_bot lines 2026-06-04
    today = [l for l in bot if "2026-06-04" in l]
    if today:
        print("\n[mina_bot.log — 2026-06-04 ilgili satırlar]")
        for ln in today:
            print(f"  {ln}")

    # all TP/trailing related raw
    rel = [l for l in bot if sym in l and re.search(r"take_profit|trailing|TP1|TP2", l, re.I)]
    if rel:
        print("\n[mina_bot.log — TP/trailing satırları]")
        for ln in rel:
            print(f"  {ln}")
    print()

for sym in SYMS:
    report_coin(sym)
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    sftp = c.open_sftp()
    try:
        sftp.stat("/root/MINA_v2/scripts")
    except FileNotFoundError:
        sftp.mkdir("/root/MINA_v2/scripts")
    with sftp.open(REMOTE_PY, "w") as f:
        f.write(LOCAL)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        f"/root/MINA_v2/venv/bin/python {REMOTE_PY}", timeout=120
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    c.close()

if __name__ == "__main__":
    main()
