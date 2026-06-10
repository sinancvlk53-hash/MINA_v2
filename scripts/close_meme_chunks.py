#!/usr/bin/env python3
"""MEMEUSDT parçalı MARKET kapama (maxQty aşımı)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dashboard"))

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from backend.config import AccountManager, BinanceConfig
from mina_position_manager import MinaPositionManager
from mina_trading_journal import TradingJournal
import dashboard_ws

SYMBOL = "MEMEUSDT"
SIDE = "LONG"


def main():
    client = BinanceConfig().get_client()
    lot_cache = dashboard_ws._build_market_lot_cache(client)
    print("limits:", lot_cache.get(SYMBOL))

    account = AccountManager(client)
    slot = account.calculate_slot_size()
    journal = TradingJournal(db_path=os.path.join(ROOT, "mina_trading_journal.db"))
    pm = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    n = dashboard_ws._close_position_market_sync(
        client,
        pm,
        SYMBOL,
        SIDE,
        lot_cache=lot_cache,
        chunk_pause=0.5,
        log_prefix="MANUAL",
    )
    journal.close()
    print(f"Toplam emir: {n}")

    raw = client.futures_position_information(symbol=SYMBOL)
    for p in raw:
        if float(p.get("positionAmt") or 0) != 0:
            print("KALAN:", p["positionAmt"])
            return 1
    print("MEMEUSDT kapalı")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
