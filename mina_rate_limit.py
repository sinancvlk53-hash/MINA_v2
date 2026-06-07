# -*- coding: utf-8 -*-
"""Ortak Binance rate-limit takibi — tüm servisler paylaşır."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

DATA_ROOT = os.environ.get(
    "MINA_DATA_ROOT",
    os.path.dirname(os.path.abspath(__file__)),
)
STATE_PATH = os.path.join(DATA_ROOT, ".binance_rate_limit.json")

# -1003 backoff: 30s → 60s → 120s
RATE_LIMIT_BACKOFF_SEC = (30, 60, 120)

# Servisler arası minimum istek aralığı (ms)
MIN_REQUEST_GAP_MS = 50


def _load() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except OSError:
        pass


def record_request(service: str = "unknown") -> None:
    """Son istek zamanını kaydet."""
    now = time.time()
    data = _load()
    data["last_request_ts"] = now
    data["last_service"] = service
    counts = data.setdefault("service_counts", {})
    counts[service] = int(counts.get(service, 0)) + 1
    _save(data)


def wait_before_request(service: str = "unknown") -> None:
    """Servisler arası minimum boşluk + aktif ban bekleme."""
    data = _load()
    ban_until = float(data.get("ban_until_ts") or 0)
    now = time.time()
    if ban_until > now:
        time.sleep(ban_until - now + 0.1)
    last = float(data.get("last_request_ts") or 0)
    gap = MIN_REQUEST_GAP_MS / 1000.0
    if last > 0 and (now - last) < gap:
        time.sleep(gap - (now - last))
    record_request(service)


def _parse_ban_until(exc: BaseException) -> Optional[float]:
    import re
    m = re.search(r"banned until (\d+)", str(exc), re.I)
    if not m:
        return None
    try:
        return int(m.group(1)) / 1000.0
    except ValueError:
        return None


def register_rate_limit_hit(exc: BaseException, attempt: int) -> float:
    """-1003 kaydı; backoff süresi döner."""
    wait = RATE_LIMIT_BACKOFF_SEC[min(attempt, len(RATE_LIMIT_BACKOFF_SEC) - 1)]
    ban_until = _parse_ban_until(exc)
    if ban_until is not None:
        wait = max(wait, ban_until - time.time() + 0.5)
    data = _load()
    data["ban_until_ts"] = time.time() + wait
    data["last_rate_limit"] = time.time()
    data["last_rate_limit_msg"] = str(exc)[:500]
    hits = int(data.get("rate_limit_hits") or 0) + 1
    data["rate_limit_hits"] = hits
    _save(data)
    return max(wait, 0.0)


def get_status() -> dict[str, Any]:
    return _load()
