# -*- coding: utf-8 -*-
"""
MINA v2 — Katman 2: Sinyal Giyotini (Confluence + Parlaklık)

Merter sinyali + Haluk makro (TOTAL yönü) + seans + SFP bayrağı → karar.
Kararlar hardcode edilmez; kurallar burada tanımlıdır.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

SESSION_BRIGHTNESS = {
    "asya": 35,
    "asia": 35,
    "londra": 55,
    "london": 55,
    "new_york": 75,
    "new york": 75,
    "ny": 75,
}

RE_TOTAL_UP = re.compile(
    r"TOTAL.*?(?:yukar|yukari|yukarı|pozitif|guclu|güçlü|devam)",
    re.IGNORECASE | re.DOTALL,
)
RE_TOTAL_DOWN = re.compile(
    r"TOTAL.*?(?:asag|aşağı|dusuk|düşük|baski|baskı|tehlike|salm)",
    re.IGNORECASE | re.DOTALL,
)
RE_SFP = re.compile(r"\$SFP\s+için", re.IGNORECASE)


def normalize_session(name: str) -> str:
    key = (name or "").strip().lower().replace(" ", "_")
    aliases = {
        "asya": "asya",
        "asia": "asya",
        "londra": "londra",
        "london": "londra",
        "new_york": "new_york",
        "newyork": "new_york",
        "ny": "new_york",
    }
    return aliases.get(key, key)


def parse_total_direction(haluk_text: str) -> Optional[str]:
    """Haluk TOTAL yorumundan yön: up | down | None."""
    if not haluk_text:
        return None
    up = bool(RE_TOTAL_UP.search(haluk_text))
    down = bool(RE_TOTAL_DOWN.search(haluk_text))
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    if re.search(r"\byukar", haluk_text, re.I) and not re.search(r"\basag|\başağı", haluk_text, re.I):
        return "up"
    if re.search(r"\basag|\başağı", haluk_text, re.I):
        return "down"
    return None


def merter_has_sfp(merter_text: str, merter_record: Optional[Dict[str, Any]] = None) -> bool:
    if RE_SFP.search(merter_text or ""):
        return True
    if merter_record:
        sym = str(merter_record.get("symbol", "")).upper()
        if sym in ("SFP", "SFPUSDT"):
            return True
    return False


def evaluate_guillotine(
    *,
    merter_record: Dict[str, Any],
    haluk_macro_text: str,
    session: str,
    merter_raw_text: str = "",
) -> Dict[str, Any]:
    """
    Katman 2 kararı.
    Returns: verdict, brightness, reason, layers_detail
    """
    session_key = normalize_session(session)
    total_dir = parse_total_direction(haluk_macro_text)
    direction = (merter_record.get("direction") or "").upper()
    has_sfp = merter_has_sfp(merter_raw_text or merter_record.get("raw_text", ""), merter_record)
    base_brightness = SESSION_BRIGHTNESS.get(session_key, 50)

    detail: Dict[str, Any] = {
        "session": session_key,
        "total_direction": total_dir,
        "merter_direction": direction,
        "has_sfp": has_sfp,
        "base_session_brightness": base_brightness,
    }

    # Makro çelişki: LONG + TOTAL aşağı → REJECT
    if direction == "LONG" and total_dir == "down":
        return {
            "layer": 2,
            "verdict": "REJECT",
            "brightness": 0,
            "label": "REJECT",
            "reason": "TOTAL aşağı — Merter LONG ile makro uyumsuz (F1)",
            "detail": detail,
        }

    # ALTIN: NY + TOTAL yukarı + LONG + SFP
    if (
        session_key == "new_york"
        and total_dir == "up"
        and direction == "LONG"
        and has_sfp
    ):
        return {
            "layer": 2,
            "verdict": "ALTIN_SİNYAL",
            "brightness": 100,
            "label": "ALTIN_SİNYAL",
            "reason": "NY seansı + TOTAL yukarı + SFP onayı",
            "detail": detail,
        }

    # Düşük parlaklık: Asya + TOTAL yukarı + SFP yok
    if (
        session_key == "asya"
        and total_dir == "up"
        and direction == "LONG"
        and not has_sfp
    ):
        brightness = min(base_brightness, 40)
        return {
            "layer": 2,
            "verdict": "QUEUE_LOW",
            "brightness": brightness,
            "label": "DÜŞÜK_PARLAKLIK",
            "reason": f"Asya seansı — parlaklık {brightness} (SFP yok)",
            "detail": detail,
        }

    # Varsayılan: kuyruğa al (orta parlaklık)
    brightness = base_brightness
    if total_dir == "up" and direction == "LONG":
        brightness = min(brightness + 10, 70)
    return {
        "layer": 2,
        "verdict": "QUEUE",
        "brightness": brightness,
        "label": "KUYRUK",
        "reason": "Standart confluence — onay kuyruğu",
        "detail": detail,
    }


def evaluate_katman3(k2: Dict[str, Any]) -> Dict[str, Any]:
    """Katman 3: motor / onay bot aksiyonu."""
    label = k2.get("label", "")
    if label == "REJECT":
        return {
            "layer": 3,
            "action": "SKIP",
            "reason": "Katman 2 REJECT — pozisyon açılmaz",
        }
    if label == "ALTIN_SİNYAL":
        return {
            "layer": 3,
            "action": "PRIORITY_OPEN",
            "reason": "Altın sinyal — öncelikli onay ve motor",
        }
    if label == "DÜŞÜK_PARLAKLIK":
        return {
            "layer": 3,
            "action": "QUEUE_LOW_PRIORITY",
            "reason": "Düşük parlaklık — bekle / düşük öncelik",
        }
    return {
        "layer": 3,
        "action": "STANDARD_QUEUE",
        "reason": "Standart onay kuyruğu",
    }
