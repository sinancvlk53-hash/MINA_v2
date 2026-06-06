# -*- coding: utf-8 -*-
"""Hayalet pozisyon tespiti — boş cüzdan hariç, motor takipsiz marjin/pozisyon."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, List, Set, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mina_tracking as mt

logger = logging.getLogger("MİNA_v2")

# symbol_side -> last alert unix time (spam önleme)
_last_alert: Dict[str, float] = {}
ALERT_COOLDOWN_SEC = 3600

# Boş cüzdan: marjin==0 ve miktar==0 → tamamen yok say (log yok)
MARGIN_ZERO_EPS = 1e-6
AMT_ZERO_EPS = 1e-8

MERTER_STATE_FILE = os.path.join(_ROOT, "signal_bot", "merter_dca_state.json")
MERTER_JOURNAL_DB = os.path.join(_ROOT, "mina_trading_journal.db")


def merter_dca_tracked_keys() -> Set[str]:
    """Merter 1x DCA yönetimindeki pozisyonlar — hayalet sayılmaz, motor TP uygulanmaz."""
    keys: Set[str] = set()
    state = mt.load_json(MERTER_STATE_FILE)
    for pos in (state.get("positions") or {}).values():
        sym = (pos.get("symbol") or "").strip().upper()
        if sym:
            keys.add(mt.pos_key(sym, "LONG"))

    try:
        import sqlite3

        if os.path.isfile(MERTER_JOURNAL_DB):
            conn = sqlite3.connect(MERTER_JOURNAL_DB)
            rows = conn.execute(
                """
                SELECT DISTINCT symbol FROM trades
                WHERE status = 'open' AND leverage = 1 AND side = 'LONG'
                  AND (signal_source = 'MZ' OR signal_source LIKE 'merter%')
                """
            ).fetchall()
            conn.close()
            for (sym,) in rows:
                if sym:
                    keys.add(mt.pos_key(str(sym).upper(), "LONG"))
    except Exception:
        pass
    return keys


def is_merter_dca_position(
    symbol: str,
    side: str,
    leverage: Optional[int] = None,
) -> bool:
    """Merter DCA (1x LONG) — motor savunma/TP/trailing devre dışı."""
    side_u = (side or "").upper()
    if side_u != "LONG":
        return False
    if leverage is not None and int(leverage) != 1:
        return False
    return mt.pos_key(symbol, side_u) in merter_dca_tracked_keys()


def is_upbit_listing_managed(symbol: str, side: str) -> bool:
    """Upbit listeleme SHORT — upbit_listing_trader yönetir, ana motor dokunmaz."""
    try:
        from signal_bot.upbit_listing_trader import is_upbit_listing_position
        return is_upbit_listing_position(symbol, side)
    except Exception:
        return False


def _position_side_key(p: Dict[str, Any]) -> str:
    sym = p.get("symbol", "")
    side = p.get("positionSide") or "BOTH"
    amt = float(p.get("positionAmt") or 0)
    if side in ("LONG", "SHORT"):
        return mt.pos_key(sym, side)
    return mt.pos_key(sym, "LONG" if amt > 0 else "SHORT")


def _tracked_keys() -> Set[str]:
    keys: Set[str] = set()
    for path in (mt.INITIAL_PRICE_FILE, mt.DEFENSE_FILE, mt.INITIAL_MARGIN_FILE):
        keys.update(mt.load_json(path).keys())
    return keys


def _is_tracked(symbol: str, side: str, tracked: Set[str]) -> bool:
    if side in ("LONG", "SHORT"):
        return mt.pos_key(symbol, side) in tracked
    return (
        mt.pos_key(symbol, "LONG") in tracked
        or mt.pos_key(symbol, "SHORT") in tracked
    )


def _is_ignored_empty_wallet(amount: float, margin: float) -> bool:
    """Marjin 0 ve miktar 0 → hayalet değil, log'a da yazma."""
    return abs(amount) <= AMT_ZERO_EPS and abs(margin) <= MARGIN_ZERO_EPS


def _qualifies_for_ghost_check(amount: float, margin: float) -> bool:
    """Hayalet kontrolü: marjin > 0 VEYA miktar ≠ 0."""
    return abs(amount) > AMT_ZERO_EPS or margin > MARGIN_ZERO_EPS


def detect_ghost_positions(raw_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Hayalet: (marjin > 0 veya miktar ≠ 0) VE motor takip etmiyor.

    Marjin 0 ve miktar 0 → tamamen yok sayılır (log/telegram yok).
    """
    ghosts: List[Dict[str, Any]] = []
    tracked = _tracked_keys()
    merter_keys = merter_dca_tracked_keys()

    for p in raw_positions:
        amt = float(p.get("positionAmt") or 0)
        margin = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
        sym = p.get("symbol", "")
        side = p.get("positionSide") or "BOTH"

        if _is_ignored_empty_wallet(amt, margin):
            continue
        if not _qualifies_for_ghost_check(amt, margin):
            continue

        pos_key = _position_side_key(p)
        if pos_key in merter_keys:
            continue

        motor_tracks = _is_tracked(sym, side, tracked)
        if motor_tracks:
            continue

        kind = "stranded_margin" if abs(amt) <= AMT_ZERO_EPS else "untracked_position"
        ghosts.append(
            {
                "symbol": sym,
                "side": side,
                "kind": kind,
                "positionAmt": amt,
                "isolatedMargin": margin,
                "isolatedWallet": float(p.get("isolatedWallet") or 0),
                "tracked_by_motor": False,
            }
        )
    return ghosts


def notify_ghost_positions(ghosts: List[Dict[str, Any]]) -> None:
    if not ghosts:
        return
    try:
        from tools.telegram_bot import send_notification
    except Exception:
        send_notification = None

    now = time.time()
    for g in ghosts:
        alert_key = f"{g['symbol']}_{g['side']}"
        if now - _last_alert.get(alert_key, 0) < ALERT_COOLDOWN_SEC:
            continue
        _last_alert[alert_key] = now

        amt = g["positionAmt"]
        margin = g["isolatedMargin"]
        if g.get("kind") == "untracked_position":
            detail = f"amt={amt} marjin={margin:.4f}"
        else:
            detail = f"amt=0 marjin={margin:.4f} (takılı cüzdan)"

        msg = (
            f"👻 *HAYALET POZİSYON*\n"
            f"`{g['symbol']}` {g['side']}\n"
            f"{detail}\n"
            f"Motor takibi: YOK — temizlik gerekebilir"
        )
        logger.warning(
            "HAYALET %s %s %s amt=%s margin=%.4f",
            g["symbol"],
            g["side"],
            g.get("kind"),
            amt,
            margin,
        )
        if send_notification:
            send_notification(msg)


def scan_and_report(client) -> List[Dict[str, Any]]:
    raw = client.futures_position_information()
    ghosts = detect_ghost_positions(raw)
    notify_ghost_positions(ghosts)
    return ghosts
