#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BÖLÜM 5 — sistem kontrol (sunucuda çalıştırılır veya SSH ile)."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
SERVICES = [
    "mina-engine",
    "mina-listener",
    "mina-merter-dca",
    "mina-queue-watcher",
    "mina-dashboard-ws",
    "mina-dashboard-vite",
    "mina-binance-listings",
    "mina-upbit-listings",
    "mina-haluk-yayin",
]
CRITICAL = re.compile(
    r"CRITICAL|Traceback|FATAL|kill-switch|HATA|ERROR|Exception|failed|başarısız",
    re.I,
)
LOG_FILES = {
    "mina-engine": f"{ROOT}/mina_bot.log",
    "mina-listener": f"{ROOT}/signal_bot/signals_log.txt",
    "mina-merter-dca": f"{ROOT}/signal_bot/merter_dca.log",
    "mina-dashboard-ws": f"{ROOT}/dashboard_ws.log",
    "mina-dashboard-vite": f"{ROOT}/vite_dashboard.log",
}


def _since_24h_lines(path: str) -> list[str]:
    if not os.path.isfile(path):
        return [f"(log yok: {path})"]
    cutoff = datetime.now() - timedelta(hours=24)
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip()
                if not line:
                    continue
                ts = None
                m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
                if m:
                    try:
                        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass
                if ts is None or ts >= cutoff:
                    if CRITICAL.search(line):
                        out.append(line)
    except OSError as e:
        out.append(f"(okuma hatası {path}: {e})")
    return out[-50:]


def scan_service_logs() -> dict:
    print("=== 10) SERVİS LOGLARI — son 24s kritik ===")
    result = {}
    for svc in SERVICES:
        print(f"\n--- {svc} ---")
        st = subprocess.run(
            ["systemctl", "is-active", f"{svc}.service"],
            capture_output=True, text=True,
        ).stdout.strip()
        print(f"status: {st}")
        log_path = LOG_FILES.get(svc)
        if log_path:
            hits = _since_24h_lines(log_path)
            result[svc] = hits
            for h in hits[:20]:
                print(h)
            if len(hits) > 20:
                print(f"... +{len(hits) - 20} satır")
        else:
            out = subprocess.run(
                ["journalctl", "-u", f"{svc}.service", "--since", "24 hours ago", "--no-pager", "-q"],
                capture_output=True, text=True, errors="replace",
            )
            hits = [l for l in out.stdout.splitlines() if CRITICAL.search(l)]
            result[svc] = hits[-30:]
            for h in hits[-15:]:
                print(h)
    return result


def check_derr_orphans() -> list:
    print("\n=== 11) DERR orphan kontrol ===")
    db = os.path.join(ROOT, "mina_trading_journal.db")
    orphans = []
    try:
        sys.path.insert(0, ROOT)
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from config import BinanceConfig
        from position_manager import PositionManager
        client = BinanceConfig().get_client()
        pm = PositionManager(client)
        open_keys = {f"{p['symbol']}_{p['side']}" for p in pm.get_all_positions()}
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, symbol, side, status FROM trades WHERE status='open'"
        ).fetchall()
        for r in rows:
            key = f"{r['symbol']}_{r['side']}"
            if key not in open_keys:
                orphans.append(dict(r))
                print(f"ORPHAN DERR id={r['id']} {r['symbol']} {r['side']} (Binance'te yok)")
        conn.close()
        if not orphans:
            print("orphan yok")
    except Exception as e:
        print(f"HATA: {e}")
    return orphans


def check_zero_margins() -> list:
    print("\n=== 12) initial_margins.json sıfır kontrol ===")
    path = os.path.join(ROOT, "initial_margins.json")
    zeros = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            try:
                if float(v or 0) <= 0:
                    zeros.append(k)
                    print(f"SIFIR margin: {k} = {v}")
            except (TypeError, ValueError):
                zeros.append(k)
                print(f"GECERSIZ margin: {k} = {v}")
        if not zeros:
            print("sıfır margin yok")
        else:
            print(f"fix_zero_initial_margins çalıştırılıyor...")
            sys.path.insert(0, ROOT)
            sys.path.insert(0, os.path.join(ROOT, "backend"))
            from mina_position_manager import MinaPositionManager
            from mina_trading_journal import TradingJournal
            from config import BinanceConfig, AccountManager
            cfg = BinanceConfig()
            client = cfg.get_client()
            slot = AccountManager(client).calculate_slot_size()
            journal = TradingJournal(db_path=os.path.join(ROOT, "mina_trading_journal.db"))
            mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)
            fixed = mina.fix_zero_initial_margins(verbose=True)
            print(f"düzeltilen: {len(fixed)}")
    except FileNotFoundError:
        print(f"(dosya yok: {path})")
    except Exception as e:
        print(f"HATA: {e}")
    return zeros


def main():
    os.chdir(ROOT)
    scan_service_logs()
    check_derr_orphans()
    check_zero_margins()


if __name__ == "__main__":
    main()
