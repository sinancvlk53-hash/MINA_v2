# -*- coding: utf-8 -*-
"""Haluk coin analizi — Binance fiyat takibi (1s / 4s / 24s)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from signal_bot.haluk_yayin_db import (
    init_yayin_tables,
    pending_price_checks,
    update_coin_baz_fiyat,
    update_coin_interval_price,
)

log = logging.getLogger(__name__)
TR_TZ = timezone(timedelta(hours=3))

_INTERVAL_HOURS = {"1s": 1, "4s": 4, "24s": 24}


def _normalize_symbol(coin: str) -> str:
    c = (coin or "").strip().upper()
    if c.endswith("USDT"):
        return c
    return f"{c}USDT"


def fetch_binance_price(coin: str) -> Optional[float]:
    """Futures ticker fiyatı — önce client, yoksa public API."""
    symbol = _normalize_symbol(coin)
    try:
        from backend.config import BinanceConfig

        client = BinanceConfig().get_client()
        return float(client.futures_symbol_ticker(symbol=symbol)["price"])
    except Exception as exc:
        log.debug("client fiyat %s: %s", symbol, exc)

    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MINA-haluk-coin/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return float(data["price"])
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        log.warning("Binance fiyat alınamadı %s: %s", symbol, exc)
        return None


def eval_basari(strateji: str, baz: float, fiyat: float) -> str:
    if not baz or not fiyat:
        return ""
    pct = (fiyat - baz) / baz * 100.0
    s = (strateji or "").lower()
    if "long" in s:
        return "OK" if pct > 0 else "FAIL"
    if "short" in s:
        return "OK" if pct < 0 else "FAIL"
    return "N/A"


def _parse_created_at(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=TR_TZ) if raw.tzinfo is None else raw
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=TR_TZ)
        except ValueError:
            continue
    return None


def capture_baz_prices_for_rows(row_ids: List[int]) -> int:
    """Yeni coin satırları için anlık baz_fiyat kaydet."""
    if not row_ids:
        return 0
    init_yayin_tables()
    from signal_bot.haluk_yayin_db import _conn

    conn = _conn()
    n = 0
    try:
        placeholders = ",".join("?" * len(row_ids))
        rows = conn.execute(
            f"SELECT id, coin FROM haluk_coin_analizleri WHERE id IN ({placeholders})",
            row_ids,
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        price = fetch_binance_price(row["coin"])
        if price is not None:
            update_coin_baz_fiyat(int(row["id"]), price)
            n += 1
            log.info("baz_fiyat %s id=%s → %.6f", row["coin"], row["id"], price)
    return n


def check_pending_coin_prices() -> int:
    """Vadesi gelen 1s/4s/24s fiyat kontrollerini çalıştır."""
    init_yayin_tables()
    now = datetime.now(TR_TZ)
    updated = 0

    for row in pending_price_checks():
        created = _parse_created_at(row.get("created_at"))
        if not created:
            continue
        baz = row.get("baz_fiyat")
        if not baz:
            continue

        for interval, hours in _INTERVAL_HOURS.items():
            price_col = f"fiyat_{interval}"
            if row.get(price_col) is not None:
                continue
            due = created + timedelta(hours=hours)
            if now < due:
                continue
            fiyat = fetch_binance_price(row["coin"])
            if fiyat is None:
                continue
            basari = eval_basari(row.get("strateji") or "", float(baz), fiyat)
            update_coin_interval_price(
                int(row["id"]),
                interval=interval,
                fiyat=fiyat,
                basari=basari,
            )
            updated += 1
            log.info(
                "fiyat_%s %s id=%s baz=%.6f now=%.6f basari=%s",
                interval, row["coin"], row["id"], baz, fiyat, basari,
            )
    return updated
