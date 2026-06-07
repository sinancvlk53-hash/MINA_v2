# -*- coding: utf-8 -*-
"""Binance API retry — -1003 ban bekleme + geçici hatalarda exponential backoff."""

from __future__ import annotations

import logging
import random
import re
import string
import time
from typing import Any, Callable

log = logging.getLogger("mina-binance-retry")

_BAN_UNTIL_RE = re.compile(r"banned until (\d+)", re.I)
_MAX_ATTEMPTS = 3
_BACKOFF_SEC = (2, 4, 8)

# Geçici sayılan kodlar (rate limit / timeout / internal)
_TRANSIENT_CODES = frozenset({
    -1003,  # Too many requests / IP ban
    -1001,  # Disconnected
    -1021,  # Timestamp
    -2010,  # NEW_ORDER_REJECTED (sometimes transient)
    503,
    504,
})


def _exc_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if code is not None:
        try:
            return int(code)
        except (TypeError, ValueError):
            pass
    msg = str(exc)
    m = re.search(r"code=-?(\d+)", msg)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _ban_wait_seconds(exc: BaseException) -> float | None:
    m = _BAN_UNTIL_RE.search(str(exc))
    if not m:
        return None
    try:
        until_ms = int(m.group(1))
    except ValueError:
        return None
    wait = (until_ms / 1000.0) - time.time()
    return max(wait, 0.0) + 0.5


def _is_transient(exc: BaseException) -> bool:
    code = _exc_code(exc)
    if code in _TRANSIENT_CODES:
        return True
    msg = str(exc).lower()
    return any(
        k in msg
        for k in ("timeout", "timed out", "connection reset", "connection aborted", "temporarily unavailable")
    )


def _service_name(func: Callable[..., Any]) -> str:
    return getattr(func, "__name__", None) or "binance"


def call_with_retry(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Max 3 deneme; proaktif rate-limit throttle + -1003 ban bekleme + 2/4/8 sn backoff."""
    last_exc: BaseException | None = None
    svc = _service_name(func)
    for attempt in range(_MAX_ATTEMPTS):
        # Proaktif throttle: servisler arası minimum boşluk + aktif ban bekleme.
        # wait_before_request kendi içinde record_request çağırır.
        try:
            from mina_rate_limit import wait_before_request
            wait_before_request(svc)
        except Exception:
            pass
        try:
            result = func(*args, **kwargs)
            try:
                from mina_rate_limit import record_request
                record_request(svc)
            except Exception:
                pass
            return result
        except Exception as exc:
            last_exc = exc
            code = _exc_code(exc)
            if code == -1003:
                # Ban bilgisini paylaşılan state'e yaz: diğer servisler de beklesin.
                try:
                    from mina_rate_limit import register_rate_limit_hit
                    register_rate_limit_hit(exc, attempt)
                except Exception:
                    pass
            if attempt >= _MAX_ATTEMPTS - 1:
                if code == -1003:
                    try:
                        from mina_system_alerts import alert_rate_limit
                        alert_rate_limit(str(exc))
                    except Exception:
                        pass
                break
            if code == -1003:
                wait = _ban_wait_seconds(exc)
                if wait is not None:
                    log.warning(
                        "Binance -1003 ban, %.1fs bekleniyor (deneme %s/%s): %s",
                        wait,
                        attempt + 1,
                        _MAX_ATTEMPTS,
                        exc,
                    )
                    time.sleep(wait)
                    continue
            if _is_transient(exc):
                delay = _BACKOFF_SEC[min(attempt, len(_BACKOFF_SEC) - 1)]
                log.warning(
                    "Binance geçici hata, %ss backoff (deneme %s/%s): %s",
                    delay,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    exc,
                )
                time.sleep(delay)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("call_with_retry: beklenmeyen durum")


def _make_client_order_id(symbol: str) -> str:
    """MINA_{symbol}{timestamp}{random4} — max 36 karakter."""
    sym = re.sub(r"[^A-Za-z0-9]", "", (symbol or "").upper())
    rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    cid = f"MINA_{sym}{int(time.time())}{rnd}"
    return cid[:36]


def _find_existing_order(client: Any, symbol: str, client_order_id: str) -> Any | None:
    if not symbol or not client_order_id:
        return None
    try:
        return client.futures_get_order(symbol=symbol, origClientOrderId=client_order_id)
    except Exception:
        pass
    try:
        for order in client.futures_get_open_orders(symbol=symbol):
            if order.get("clientOrderId") == client_order_id:
                return order
    except Exception:
        pass
    return None


def idempotent_futures_create_order(client: Any, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """clientOrderId ile çift emir gönderimini engelle."""
    symbol = kwargs.get("symbol")
    if symbol is None and args:
        symbol = args[0]

    cid = kwargs.get("newClientOrderId")
    if not cid and symbol:
        cid = _make_client_order_id(str(symbol))
        kwargs["newClientOrderId"] = cid

    if cid and symbol:
        existing = _find_existing_order(client, str(symbol), str(cid))
        if existing:
            log.info(
                "Idempotent emir atlandı — mevcut orderId=%s clientOrderId=%s",
                existing.get("orderId"),
                cid,
            )
            return existing

    return call_with_retry(func, *args, **kwargs)


class RetryBinanceClient:
    """Client proxy — futures_* ve ilgili çağrılar otomatik retry."""

    _WRAP_PREFIXES = ("futures_", "get_server_time", "get_account", "ping")
    _ALWAYS_WRAP = frozenset({
        "futures_position_information",
        "futures_mark_price",
        "futures_create_order",
        "futures_cancel_order",
        "futures_get_order",
        "futures_exchange_info",
        "futures_klines",
        "futures_account_balance",
        "futures_get_open_orders",
        "futures_change_leverage",
        "futures_change_margin_type",
        "futures_symbol_ticker",
    })

    def __init__(self, client: Any) -> None:
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name: str) -> Any:
        client = object.__getattribute__(self, "_client")
        attr = getattr(client, name)
        if not callable(attr):
            return attr
        if name == "futures_create_order":
            def _create(*args: Any, **kwargs: Any) -> Any:
                return idempotent_futures_create_order(client, attr, *args, **kwargs)
            return _create
        if name in self._ALWAYS_WRAP or any(name.startswith(p) for p in self._WRAP_PREFIXES):
            def _wrapped(*args: Any, **kwargs: Any) -> Any:
                return call_with_retry(attr, *args, **kwargs)
            return _wrapped
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._client, name, value)


def wrap_binance_client(client: Any) -> Any:
    """Ham Binance Client → retry proxy."""
    if isinstance(client, RetryBinanceClient):
        return client
    return RetryBinanceClient(client)
