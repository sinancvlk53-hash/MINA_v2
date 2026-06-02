# -*- coding: utf-8 -*-
"""
Üretim bootstrap: Binance Testnet gerçek fiyatları → state JSON + DERR DB + max_prices seed.
Her adım ham çıktı üretir.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import BinanceConfig, AccountManager  # noqa: E402
from position_manager import PositionManager  # noqa: E402
from mina_position_manager import MinaPositionManager  # noqa: E402
from mina_trading_journal import TradingJournal  # noqa: E402
import mina_tracking as mt  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("BOOTSTRAP — ÖNCE (mevcut state)")
    print("=" * 70)
    mt.dump_all_tracking()

    cfg = BinanceConfig()
    client = cfg.get_client()
    account = AccountManager(client)
    pm = PositionManager(client)
    slot = account.calculate_slot_size()

    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    journal = TradingJournal(db_path=db_path)
    print(f"\n>>> DERR DB: {db_path} (exists={os.path.exists(db_path)})")

    mina = MinaPositionManager(client, slot, journal=journal)
    report = mina.sync_reality_from_binance(verbose=True)

    print("\n" + "=" * 70)
    print("BOOTSTRAP — SONRA (güncellenmiş state)")
    print("=" * 70)
    mt.dump_all_tracking()

    print("\n>>> SYNC REPORT:")
    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))

    cursor = journal.conn.cursor()
    cursor.execute("SELECT id, symbol, side, status, open_price FROM trades ORDER BY id")
    rows = cursor.fetchall()
    print("\n>>> DERR trades table:")
    for row in rows:
        print(dict(row))

    journal.close()


if __name__ == "__main__":
    main()
