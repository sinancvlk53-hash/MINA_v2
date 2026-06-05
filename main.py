# -*- coding: utf-8 -*-
"""
MİNA v2 — TEK MOTOR giriş noktası (mina_position_manager.py çekirdek).
Eski engine/main.py _archive altına taşındı.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import BinanceConfig, AccountManager  # noqa: E402
from position_manager import PositionManager  # noqa: E402
from mina_position_manager import MinaPositionManager  # noqa: E402
from mina_trading_journal import TradingJournal  # noqa: E402
import mina_tracking as mt  # noqa: E402
from ghost_positions import scan_and_report  # noqa: E402
from mina_entry_orders import cancel_stale_pending_limits, process_pending_limit_fills  # noqa: E402

LOG_PATH = os.path.join(ROOT, "mina_bot.log")
logger = logging.getLogger("MİNA_v2")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)


def run() -> None:
    print("=" * 70)
    print("MİNA v2 — TEK ÇEKİRDEK MOTOR (MinaPositionManager)")
    print("=" * 70)

    cfg = BinanceConfig()
    client = cfg.get_client()
    account = AccountManager(client)
    pm = PositionManager(client)
    slot = account.calculate_slot_size()

    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    journal = TradingJournal(db_path=db_path)
    mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    lock_path = os.path.join(ROOT, "engine.lock")
    with open(lock_path, "w", encoding="utf-8") as lf:
        lf.write(str(os.getpid()))
    logger.info("engine.lock yazıldı pid=%s", os.getpid())

    print("\n>>> BOOTSTRAP (Binance gerçeklik senkronu)")
    report = mina.sync_reality_from_binance(verbose=True)
    print(report)
    mt.dump_all_tracking()

    ghosts = scan_and_report(client)
    if ghosts:
        print(f"⚠️  {len(ghosts)} hayalet pozisyon tespit edildi (log + Telegram)")

    interval = int(os.environ.get("MINA_CHECK_INTERVAL", "30"))
    logger.info("Motor başladı — interval=%ss", interval)

    while True:
        try:
            cancel_stale_pending_limits(client)
            filled = process_pending_limit_fills(mina)
            if filled:
                print(f"  📥 {filled} bekleyen limit emri doldu → tracking seed")
            positions = pm.get_all_positions()
            ghosts = scan_and_report(client)
            if ghosts:
                print(f"  👻 Hayalet: {', '.join(g['symbol'] + '/' + g['side'] for g in ghosts)}")
            if not positions:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Açık pozisyon yok.")
            else:
                print(f"\n{'='*70}\n⏰ {datetime.now().strftime('%H:%M:%S')} — {len(positions)} pozisyon\n{'='*70}")
                for pos in positions:
                    symbol = pos["symbol"]
                    price = float(pos["mark_price"])
                    action = mina.evaluate_position(pos, price)
                    if action.get("action") != "hold":
                        logger.info("%s %s", symbol, action)
                        print(f"  ⚡ {symbol} {action}")
                        mina.execute_action(pos, action, price)
                    else:
                        side = pos["side"]
                        iep = mt.load_json(mt.INITIAL_PRICE_FILE).get(mt.pos_key(symbol, side))
                        d1 = iep * 0.95 if iep and side == "LONG" else None
                        print(
                            f"  {symbol} {side} {pos['leverage']}x "
                            f"entry={pos['entry_price']} mark={price} "
                            f"initial_ref={iep} d1_line={d1}"
                        )
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            journal.close()
            break
        except Exception as exc:
            logger.exception("Döngü hatası: %s", exc)
            time.sleep(interval)


if __name__ == "__main__":
    run()
