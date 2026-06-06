# -*- coding: utf-8 -*-
"""Makro panel seviyeleri — PDF + Telegram birleşik store."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
MACRO_LEVELS_FILE = os.path.join(SIGNAL_BOT_DIR, "macro_levels.json")

# Dashboard sabit sırası
MACRO_PANEL_COINS: tuple[str, ...] = (
    "TOTAL",
    "OTHERS",
    "BTC.D",
    "USDT.D",
    "BTCUSDT",
    "ETHUSDT",
    "XAUUSDT",
    "XAGUSDT",
    "BRENT",
    "TOTAL2",
    "TOTAL3",
)

_PANEL_ALIASES: Dict[str, str] = {
    "DIGER": "OTHERS",
    "DİĞER": "OTHERS",
    "OTHER": "OTHERS",
    "BTCD": "BTC.D",
    "BTC D": "BTC.D",
    "USDTD": "USDT.D",
    "USDT D": "USDT.D",
    "BTC": "BTCUSDT",
    "BITCOIN": "BTCUSDT",
    "ETH": "ETHUSDT",
    "XAU": "XAUUSDT",
    "XAG": "XAGUSDT",
    "GOLD": "XAUUSDT",
    "SILVER": "XAGUSDT",
}


def panel_key_for(raw: str) -> Optional[str]:
    """Ham coin/token → panel anahtarı veya None."""
    token = (raw or "").strip().upper().replace("$", "")
    token = token.replace("USDT", "")
    if token in _PANEL_ALIASES:
        token = _PANEL_ALIASES[token].replace("USDT", "")
    if token.endswith(".D"):
        key = token
    elif f"{token}USDT" in MACRO_PANEL_COINS:
        key = f"{token}USDT"
    elif token in MACRO_PANEL_COINS:
        key = token
    else:
        return None
    return key if key in MACRO_PANEL_COINS else None


def detect_panel_coins_in_text(text: str) -> List[str]:
    """Telegram metninde geçen panel coin'leri (sıralı, tekrarsız)."""
    upper = text.upper()
    found: List[str] = []
    seen: set = set()

    patterns = [
        (r"\bTOTAL3\b", "TOTAL3"),
        (r"\bTOTAL2\b", "TOTAL2"),
        (r"\bBTC\.?\s*D\b", "BTC.D"),
        (r"\bUSDT\.?\s*D\b", "USDT.D"),
        (r"\bOTHERS\b|\bDİĞER\b|\bDIGER\b", "OTHERS"),
        (r"\bTOTAL\b", "TOTAL"),
        (r"\bBRENT\b", "BRENT"),
        (r"\bBTCUSDT\b|\bBITCOIN\b|\bBTC\b", "BTCUSDT"),
        (r"\bETHUSDT\b|\bETH\b", "ETHUSDT"),
        (r"\bXAUUSDT\b|\bXAU\b", "XAUUSDT"),
        (r"\bXAGUSDT\b|\bXAG\b", "XAGUSDT"),
    ]
    for pat, key in patterns:
        if re.search(pat, upper, re.I) and key not in seen:
            seen.add(key)
            found.append(key)
    return found


def _sort_levels_desc(values: List[float]) -> List[float]:
    """Destek/direnç — büyükten küçüğe (2.25T → 1.91T)."""
    try:
        return sorted({float(v) for v in (values or [])}, reverse=True)
    except (TypeError, ValueError):
        return []


def _empty_slot(coin: str) -> Dict[str, Any]:
    return {
        "coin": coin,
        "supports": [],
        "resistances": [],
        "snippet": "",
        "direction": None,
        "source": None,
        "updated_at": None,
    }


def load_macro_levels() -> Dict[str, Any]:
    if not os.path.isfile(MACRO_LEVELS_FILE):
        return {"levels": [], "updated_at": None, "source": None}
    try:
        with open(MACRO_LEVELS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"levels": [], "updated_at": None, "source": None}


def merge_macro_levels(incoming: List[Dict[str, Any]], source: str) -> None:
    """
    Birikimli birleştir: yalnızca incoming'de geçen semboller güncellenir.
    Bahsedilmeyen semboller eski snippet/SR/direction/source değerlerini korur.
    """
    existing = load_macro_levels()
    by_coin: Dict[str, Dict[str, Any]] = {}
    for row in existing.get("levels") or []:
        key = row.get("coin")
        if key:
            by_coin[key] = dict(row)

    # Dosyada hiç kaydı olmayan slotlar için boş şablon (sıfırlama değil)
    for c in MACRO_PANEL_COINS:
        by_coin.setdefault(c, _empty_slot(c))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    touched: set[str] = set()

    for m in incoming:
        key = panel_key_for(str(m.get("coin", "")))
        if not key:
            key = m.get("coin")
        if key not in MACRO_PANEL_COINS:
            continue

        touched.add(key)
        prev = by_coin.get(key) or _empty_slot(key)
        snippet_in = (m.get("text") or m.get("snippet") or "").strip()[:400]

        supports = list(prev.get("supports") or [])
        resistances = list(prev.get("resistances") or [])
        if isinstance(m.get("supports"), list) and m["supports"]:
            supports = list(m["supports"])
        if isinstance(m.get("resistances"), list) and m["resistances"]:
            resistances = list(m["resistances"])

        by_coin[key] = {
            "coin": key,
            "supports": _sort_levels_desc(supports),
            "resistances": _sort_levels_desc(resistances),
            "direction": m["direction"] if m.get("direction") is not None else prev.get("direction"),
            "snippet": snippet_in if snippet_in else (prev.get("snippet") or ""),
            "source": source,
            "updated_at": now,
        }

    payload = {
        "updated_at": now if touched else existing.get("updated_at"),
        "source": source if touched else existing.get("source"),
        "levels": [by_coin[c] for c in MACRO_PANEL_COINS],
    }
    os.makedirs(os.path.dirname(MACRO_LEVELS_FILE), exist_ok=True)
    with open(MACRO_LEVELS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def panel_levels_for_dashboard() -> List[Dict[str, Any]]:
    """Her panel coin için satır döndür (boş slot dahil)."""
    data = load_macro_levels()
    by_coin = {r.get("coin"): r for r in (data.get("levels") or []) if r.get("coin")}
    out: List[Dict[str, Any]] = []
    for c in MACRO_PANEL_COINS:
        row = dict(by_coin.get(c) or _empty_slot(c))
        row["supports"] = _sort_levels_desc(row.get("supports") or [])
        row["resistances"] = _sort_levels_desc(row.get("resistances") or [])
        out.append(row)
    return out
