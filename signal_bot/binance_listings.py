# -*- coding: utf-8 -*-
"""Binance USDT-M perpetual yeni listeleme — mainnet public API, cache, Telegram alarm."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_PATH = os.path.join(ROOT, "signal_bot", "binance_listings_cache.json")
KNOWN_PATH = os.path.join(ROOT, "signal_bot", "binance_listings_known.json")
FAPI_BASE = "https://fapi.binance.com"

LISTING_DAYS = int(os.environ.get("LISTING_DAYS", "50"))
CACHE_TTL_SEC = int(os.environ.get("BINANCE_LISTINGS_CACHE_TTL", str(6 * 3600)))
WATCH_INTERVAL_SEC = int(os.environ.get("BINANCE_LISTINGS_WATCH_SEC", str(15 * 60)))

TR_TZ = timezone(timedelta(hours=3))


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def fmt_listing_time(ms: int) -> str:
    if not ms:
        return "—"
    return datetime.fromtimestamp(ms / 1000, tz=TR_TZ).strftime("%Y-%m-%d %H:%M")


def fetch_exchange_info() -> dict:
    r = requests.get(f"{FAPI_BASE}/fapi/v1/exchangeInfo", timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_tickers() -> Dict[str, float]:
    r = requests.get(f"{FAPI_BASE}/fapi/v1/ticker/price", timeout=30)
    r.raise_for_status()
    out: Dict[str, float] = {}
    for row in r.json():
        sym = row.get("symbol")
        if sym:
            out[sym] = float(row.get("price") or 0)
    return out


def fetch_kline_close(symbol: str, start_ms: int) -> Optional[float]:
    try:
        r = requests.get(
            f"{FAPI_BASE}/fapi/v1/klines",
            params={"symbol": symbol, "interval": "1h", "startTime": start_ms, "limit": 1},
            timeout=15,
        )
        r.raise_for_status()
        kl = r.json()
        if kl:
            return float(kl[0][4])
    except Exception:
        pass
    return None


def trading_perpetual_usdt_map(info: dict) -> Dict[str, int]:
    """symbol -> onboardDate ms"""
    out: Dict[str, int] = {}
    for s in info.get("symbols", []):
        sym = str(s.get("symbol") or "")
        if not sym.endswith("USDT"):
            continue
        if s.get("contractType") != "PERPETUAL":
            continue
        if s.get("status") != "TRADING":
            continue
        out[sym] = int(s.get("onboardDate") or 0)
    return out


def build_recent_listings(days: int = LISTING_DAYS) -> Dict[str, Any]:
    cutoff_ms = int((time.time() - days * 86400) * 1000)
    info = fetch_exchange_info()
    sym_map = trading_perpetual_usdt_map(info)
    tickers = fetch_tickers()

    coins: List[Dict[str, Any]] = []
    for sym, onboard in sym_map.items():
        if onboard < cutoff_ms:
            continue
        coin = sym.replace("USDT", "")
        price_then = fetch_kline_close(sym, onboard) if onboard else None
        price_now = tickers.get(sym)
        entry: Dict[str, Any] = {
            "coin": coin,
            "symbol": sym,
            "listedAt": fmt_listing_time(onboard),
            "onboardDateMs": onboard,
            "priceThen": price_then,
            "priceNow": price_now,
            "priceChangePct": None,
        }
        if price_then and price_now and price_then > 0:
            entry["priceChangePct"] = round((price_now - price_then) / price_then * 100, 2)
        coins.append(entry)

    coins.sort(key=lambda x: x.get("onboardDateMs") or 0, reverse=True)
    return {
        "updatedAt": int(time.time()),
        "updatedAtDisplay": datetime.now(tz=TR_TZ).strftime("%Y-%m-%d %H:%M"),
        "days": days,
        "source": "mainnet-public",
        "coins": coins,
        "total": len(coins),
    }


def refresh_cache_if_stale(force: bool = False) -> Dict[str, Any]:
    cached = _read_json(CACHE_PATH, {})
    age = time.time() - float(cached.get("updatedAt") or 0)
    if not force and cached.get("coins") is not None and age < CACHE_TTL_SEC:
        return cached
    data = build_recent_listings()
    _write_json(CACHE_PATH, data)
    return data


def get_cached_listings(force_refresh: bool = False) -> Dict[str, Any]:
    return refresh_cache_if_stale(force=force_refresh)


def load_known() -> Dict[str, Any]:
    return _read_json(KNOWN_PATH, {"seeded": False, "symbols": []})


def save_known(data: Dict[str, Any]) -> None:
    data["updatedAt"] = int(time.time())
    _write_json(KNOWN_PATH, data)


def send_listing_telegram(coin: str, listed_at: str) -> bool:
    try:
        from mina_dashboard_settings import load_settings
        if not load_settings().get("telegramNotify", True):
            return False
    except Exception:
        pass

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    text = (
        f"🚀 YENİ LİSTELEME! {coin} Binance Futures'a eklendi! "
        f"Listeleme saati: {listed_at}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        return True
    except Exception as exc:
        print(f"[BINANCE LISTINGS] Telegram hatası: {exc}")
        return False


def check_new_listings_alert() -> List[str]:
    """exchangeInfo ile yeni sembol tara; ilk çalıştırmada seed (alarm yok)."""
    info = fetch_exchange_info()
    current = trading_perpetual_usdt_map(info)
    known_data = load_known()
    known_set: Set[str] = set(known_data.get("symbols") or [])

    if not known_data.get("seeded"):
        save_known({"seeded": True, "symbols": sorted(current.keys())})
        print(f"[BINANCE LISTINGS] İlk seed: {len(current)} sembol kaydedildi (alarm yok)")
        return []

    new_symbols = sorted(set(current.keys()) - known_set)
    if not new_symbols:
        return []

    alerted: List[str] = []
    for sym in new_symbols:
        coin = sym.replace("USDT", "")
        listed_at = fmt_listing_time(current.get(sym, 0))
        if send_listing_telegram(coin, listed_at):
            print(f"[BINANCE LISTINGS] Alarm gönderildi: {coin} @ {listed_at}")
        else:
            print(f"[BINANCE LISTINGS] Alarm atlanamadı (Telegram kapalı?): {coin}")
        known_set.add(sym)
        alerted.append(sym)

    save_known({"seeded": True, "symbols": sorted(known_set)})
    if alerted:
        refresh_cache_if_stale(force=True)
    return alerted


def watcher_cycle() -> None:
    check_new_listings_alert()
    refresh_cache_if_stale(force=False)
