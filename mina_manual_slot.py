# -*- coding: utf-8 -*-
"""Manuel açılış — otomatik slot seçimi (motor vs Merter DCA)."""

from __future__ import annotations

import json
import os
from typing import Optional, Tuple

from mina_slot_policy import (
    MOTOR_SLOT_MAX,
    MERTER_DCA_YUVAS,
)

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
MERter_STATE = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")


def _merter_state() -> dict:
    try:
        with open(MERter_STATE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"positions": {}}


def merter_occupied_symbols() -> set:
    syms = set()
    for p in (_merter_state().get("positions") or {}).values():
        sym = p.get("symbol")
        if sym:
            syms.add(str(sym).upper())
    return syms


def count_merter_dca_used() -> int:
    positions = (_merter_state().get("positions") or {})
    return sum(1 for y in MERTER_DCA_YUVAS if positions.get(y))


def first_free_merter_yuva() -> Optional[str]:
    positions = (_merter_state().get("positions") or {})
    for yuva in MERTER_DCA_YUVAS:
        if not positions.get(yuva):
            return yuva
    return None


def count_motor_positions(client) -> int:
    """Dashboard ile uyumlu: Merter 1x DCA hariç açık pozisyon sayısı."""
    merter_syms = merter_occupied_symbols()
    n = 0
    for p in client.futures_position_information():
        amt = float(p.get("positionAmt") or 0)
        if amt == 0:
            continue
        sym = str(p["symbol"]).upper()
        side = "LONG" if amt > 0 else "SHORT"
        lev = int(p.get("leverage") or 0)
        if sym in merter_syms and lev == 1 and side == "LONG":
            continue
        n += 1
    return n


def slot_target_for_leverage(leverage: int) -> str:
    """1x → merter DCA, diğerleri → motor."""
    return "merter" if int(leverage) == 1 else "motor"


def check_manual_slot(
    client,
    leverage: int,
    side: str = "LONG",
) -> Tuple[bool, str, Optional[str]]:
    """
    Manuel açılış için slot kontrolü.
    Döner: (ok, mesaj, merter_yuva veya 'motor')
    """
    target = slot_target_for_leverage(leverage)
    if target == "merter":
        if str(side).upper() != "LONG":
            return False, "Merter DCA yalnızca LONG destekler", None
        used = count_merter_dca_used()
        yuva = first_free_merter_yuva()
        if not yuva:
            return False, f"Merter DCA slot dolu ({used}/{len(MERTER_DCA_YUVAS)})", None
        return True, f"Merter DCA → {yuva}", yuva

    used = count_motor_positions(client)
    if used >= MOTOR_SLOT_MAX:
        return False, f"Motor slot dolu ({used}/{MOTOR_SLOT_MAX})", None
    return True, f"Motor slot ({used + 1}/{MOTOR_SLOT_MAX})", "motor"
