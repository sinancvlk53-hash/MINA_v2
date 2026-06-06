#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance'te kapalı, DERR'de açık hayalet kayıtları Reconciliation ile kapat."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import BinanceConfig, AccountManager
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal


def main() -> None:
    client = BinanceConfig().get_client()
    account = AccountManager(client)
    slot = account.calculate_slot_size()
    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    journal = TradingJournal(db_path=db_path)
    mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    open_keys = mina.get_binance_open_keys()
    print(f"Binance acik pozisyon: {len(open_keys)}")
    for key in sorted(open_keys):
        print(f"  {key}")

    cursor = journal.conn.cursor()
    cursor.execute(
        "SELECT id, symbol, side FROM trades WHERE status='open' ORDER BY id"
    )
    before = cursor.fetchall()
    print(f"DERR acik (once): {len(before)}")
    for row in before:
        print(f"  id={row['id']} {row['symbol']} {row['side']}")

    closed = mina.reconcile_derr_with_binance(verbose=True)
    print(f"\nKapatilan: {len(closed)}")
    for r in closed:
        print(f"  id={r['trade_id']} {r['key']} pnl={r.get('pnl_usdt')}")

    cursor.execute(
        "SELECT id, symbol, side FROM trades WHERE status='open' ORDER BY id"
    )
    after = cursor.fetchall()
    print(f"DERR acik (sonra): {len(after)}")
    journal.close()


if __name__ == "__main__":
    main()
