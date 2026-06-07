# -*- coding: utf-8 -*-
"""futures_exchange_info önbelleği — 1 saat TTL, tüm modüller paylaşır."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

DATA_ROOT = os.environ.get(
    "MINA_DATA_ROOT",
    os.path.dirname(os.path.abspath(__file__)),
)
CACHE_FILE = os.path.join(DATA_ROOT, ".futures_exchange_info_cache.json")
TTL_SEC = 3600  # 1 saat


def _read_disk() -> Optional[dict]:
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            blob = json.load(f)
        if not isinstance(blob, dict):
            return None
        ts = float(blob.get("ts") or 0)
        if time.time() - ts >= TTL_SEC:
            return None
        data = blob.get("data")
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None


def _write_disk(data: dict) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f)
    except OSError:
        pass


_mem: dict = {"ts": 0.0, "data": None}


def get_futures_exchange_info(client: Any, *, force: bool = False) -> dict:
    """Önbellekten veya API'den exchange info."""
    from mina_rate_limit import wait_before_request, record_request

    now = time.time()
    if not force:
        if _mem.get("data") and now - float(_mem.get("ts") or 0) < TTL_SEC:
            return _mem["data"]
        disk = _read_disk()
        if disk:
            _mem["ts"] = now
            _mem["data"] = disk
            return disk

    wait_before_request("exchange_info")
    info = client.futures_exchange_info()
    record_request("exchange_info")
    _mem["ts"] = now
    _mem["data"] = info
    _write_disk(info)
    return info


def symbol_filters(client: Any, symbol: str) -> Dict[str, float]:
    """LOT_SIZE step + PRICE_FILTER tick."""
    info = get_futures_exchange_info(client)
    step, tick = 0.001, 0.01
    for s in info.get("symbols") or []:
        if s.get("symbol") != symbol:
            continue
        for f in s.get("filters") or []:
            ft = f.get("filterType")
            if ft == "LOT_SIZE":
                step = float(f.get("stepSize") or step)
            elif ft == "PRICE_FILTER":
                tick = float(f.get("tickSize") or tick)
        break
    return {"stepSize": step, "tickSize": tick}
