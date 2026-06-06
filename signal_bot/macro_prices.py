# -*- coding: utf-8 -*-
"""Makro panel canlı fiyatları — Binance mark + CoinGecko global (indeksler)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from signal_bot.macro_levels_store import MACRO_PANEL_COINS

log = logging.getLogger(__name__)

_COINGECKO_GLOBAL = "https://api.coingecko.com/api/v3/global"

_CACHE: Dict[str, Any] = {"ts": 0.0, "prices": {}}
_CACHE_TTL = 45
_COINGECKO_CACHE: Dict[str, Any] = {"ts": 0.0, "parsed": {}}
_COINGECKO_TTL = 300  # 5 dk — rate limit koruması

_BINANCE_SYMBOLS = {
    "BTCUSDT": "BTCUSDT",
    "ETHUSDT": "ETHUSDT",
    "XAUUSDT": "XAUUSDT",
    "XAGUSDT": "XAGUSDT",
}


def _http_json(url: str, timeout: int = 12, retries: int = 2) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "MINA-macro/1.0"})
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt + 1 < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last_exc = exc
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("http_json failed")


def _binance_mark(client, symbol: str) -> Optional[float]:
    try:
        r = client.futures_mark_price(symbol=symbol)
        return float(r["markPrice"])
    except Exception as exc:
        log.debug("mark %s: %s", symbol, exc)
        return None


def _parse_coingecko_global(g: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Tek global yanıttan TOTAL + diğer indeksler."""
    out: Dict[str, Optional[float]] = {
        "TOTAL": None,
        "TOTAL2": None,
        "TOTAL3": None,
        "OTHERS": None,
        "BTC.D": None,
        "USDT.D": None,
    }
    try:
        total = float(str(g["total_market_cap"]["usd"]).replace(",", ""))
        pct = g.get("market_cap_percentage") or {}
        btc_pct = float(pct.get("btc") or 0)
        eth_pct = float(pct.get("eth") or 0)
        usdt_pct = float(pct.get("usdt") or 0)

        btc_cap = total * btc_pct / 100.0
        eth_cap = total * eth_pct / 100.0

        out["TOTAL"] = round(total / 1_000_000_000_000, 6)
        out["TOTAL2"] = round((total - btc_cap) / 1_000_000_000_000, 6)
        out["TOTAL3"] = round((total - btc_cap - eth_cap) / 1_000_000_000_000, 6)
        out["BTC.D"] = round(btc_pct, 4)
        out["USDT.D"] = round(usdt_pct, 4)
    except Exception as exc:
        log.warning("coingecko global parse: %s", exc)
    return out


def _fetch_coingecko_indices() -> Dict[str, Optional[float]]:
    """CoinGecko global — tek istek, 5 dk cache."""
    now = time.time()
    if _COINGECKO_CACHE["parsed"] and now - _COINGECKO_CACHE["ts"] < _COINGECKO_TTL:
        return dict(_COINGECKO_CACHE["parsed"])

    parsed: Dict[str, Optional[float]] = {
        "TOTAL": None,
        "TOTAL2": None,
        "TOTAL3": None,
        "OTHERS": None,
        "BTC.D": None,
        "USDT.D": None,
    }
    try:
        payload = _http_json(_COINGECKO_GLOBAL)
        parsed = _parse_coingecko_global(payload["data"])
        try:
            top10 = _http_json(
                "https://api.coingecko.com/api/v3/coins/markets"
                "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
            )
            total_usd = float(str(payload["data"]["total_market_cap"]["usd"]).replace(",", ""))
            top10_sum = sum(float(c.get("market_cap") or 0) for c in top10)
            parsed["OTHERS"] = round(max(0.0, total_usd - top10_sum) / 1e9, 4)
        except Exception as exc:
            log.debug("coingecko top10 skip: %s", exc)
    except Exception as exc:
        log.warning("coingecko global: %s", exc)
        if _COINGECKO_CACHE["parsed"]:
            return dict(_COINGECKO_CACHE["parsed"])

    _COINGECKO_CACHE["ts"] = now
    _COINGECKO_CACHE["parsed"] = parsed
    return dict(parsed)


def format_macro_price(coin: str, value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if coin in ("BTC.D", "USDT.D"):
        return f"{value:.2f}%"
    if coin in ("TOTAL", "TOTAL2", "TOTAL3"):
        return f"{value:.3f}T"
    if coin == "OTHERS":
        return f"{value:.2f}B"
    if coin in ("BTCUSDT", "ETHUSDT"):
        return f"${value:,.2f}"
    if coin in ("XAUUSDT", "XAGUSDT"):
        return f"${value:,.0f}"
    if coin == "BRENT":
        return f"${value:.2f}"
    return f"{value:.4f}"


def fetch_macro_prices(client) -> Dict[str, Dict[str, Any]]:
    """coin -> {value, display}"""
    now = time.time()
    if now - _CACHE["ts"] < _CACHE_TTL and _CACHE["prices"]:
        return dict(_CACHE["prices"])

    prices: Dict[str, Dict[str, Any]] = {}

    for coin, sym in _BINANCE_SYMBOLS.items():
        val = _binance_mark(client, sym)
        if val is not None:
            prices[coin] = {"value": val, "display": format_macro_price(coin, val)}

    for coin, val in _fetch_coingecko_indices().items():
        if val is not None:
            prices[coin] = {"value": val, "display": format_macro_price(coin, val)}

    brent = _binance_mark(client, "BRENTUSDT")
    if brent is not None:
        prices["BRENT"] = {"value": brent, "display": format_macro_price("BRENT", brent)}

    for coin in MACRO_PANEL_COINS:
        prices.setdefault(coin, {"value": None, "display": None})

    _CACHE["ts"] = now
    _CACHE["prices"] = prices
    return dict(prices)
