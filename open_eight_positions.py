# -*- coding: utf-8 -*-
"""Testnet: 4 LONG + 4 SHORT, dinamik slot %20, 4x isolated."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

from open_fast_coins import (
    ENTRY_SLOT_RATIO,
    LEVERAGE,
    SLOT_COUNT,
    AccountManager,
    BinanceConfig,
    ensure_hedge_mode,
    get_step_sizes,
    try_open_with_backup,
)

LONG_PLAN = [
    ("SOLUSDT", "AAVEUSDT"),
    ("NEARUSDT", "AAVEUSDT"),
    ("LINKUSDT", "AAVEUSDT"),
    ("INJUSDT", "AAVEUSDT"),
]
SHORT_PLAN = [
    ("XRPUSDT", "MATICUSDT"),
    ("ADAUSDT", "MATICUSDT"),
    ("DOTUSDT", "MATICUSDT"),
    ("AVAXUSDT", "MATICUSDT"),
]
# MATIC testnette kapalı olabilir → POLUSDT yedek
SHORT_BACKUP_ALT = "POLUSDT"


def _connect(max_attempts: int = 8, wait_s: float = 3.0):
    """Spot testnet ping 502 verebilir — ping atlanır, futures balance ile doğrulanır."""
    import os
    from binance.client import Client
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

    def _noop_ping(self):
        return {}

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            Client.ping = _noop_ping
            client = Client(api_key, api_secret, testnet=testnet)
            account = AccountManager(client)
            client.futures_account_balance()
            return None, client, account
        except Exception as e:
            last_err = e
            print(f"CONNECT_ATTEMPT {attempt}/{max_attempts} err={e}")
            if attempt < max_attempts:
                time.sleep(wait_s)
    raise last_err


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    config, client, account = _connect()

    balance = account.get_usdt_balance()
    slot_size = balance / SLOT_COUNT
    margin_usdt = slot_size * ENTRY_SLOT_RATIO

    print(f"BALANCE_USDT={balance:.4f}")
    print(f"SLOT_SIZE={slot_size:.4f}")
    print(f"ENTRY_MARGIN={margin_usdt:.4f}")
    print(f"LEVERAGE={LEVERAGE}x ISOLATED\n")

    ensure_hedge_mode(client)
    step_sizes = get_step_sizes(client)
    exclude: set = set()
    opened = 0

    for primary, backup in LONG_PLAN:
        for attempt in range(1, 3):
            if try_open_with_backup(client, primary, backup, "LONG", margin_usdt, step_sizes, exclude):
                opened += 1
                break
            print(f"RETRY_LONG {primary} attempt={attempt}")
            time.sleep(1.5)
        time.sleep(0.5)

    for primary, backup in SHORT_PLAN:
        ok = False
        for attempt in range(1, 3):
            ok = try_open_with_backup(client, primary, backup, "SHORT", margin_usdt, step_sizes, exclude)
            if ok:
                break
            if backup == "MATICUSDT":
                ok = try_open_with_backup(
                    client, primary, SHORT_BACKUP_ALT, "SHORT", margin_usdt, step_sizes, exclude
                )
                if ok:
                    break
            print(f"RETRY_SHORT {primary} attempt={attempt}")
            time.sleep(1.5)
        if ok:
            opened += 1
        time.sleep(0.5)

    balance_after = account.get_usdt_balance()
    all_pos = client.futures_position_information()
    open_positions = [
        p for p in all_pos if float(p.get("positionAmt", 0)) != 0
    ]
    open_count = len(open_positions)

    print(f"\nPOSITIONS_OPENED_THIS_RUN={opened}")
    print(f"FINAL_OPEN_POSITION_COUNT={open_count}")
    print(f"FINAL_BALANCE_USDT={balance_after:.4f}")


if __name__ == "__main__":
    main()
