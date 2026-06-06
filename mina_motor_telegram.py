# -*- coding: utf-8 -*-
"""Gerçek motor olayları — Telegram bildirim şablonları."""

from __future__ import annotations

from typing import Optional


def _coin(symbol: str) -> str:
    return str(symbol or "").replace("USDT", "")


def _fmt_price(price: float) -> str:
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"


def _fmt_usdt(value: float, *, signed: bool = True) -> str:
    if signed:
        return f"{value:+.2f}"
    return f"{abs(value):.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:+.1f}"


def _send(text: str) -> None:
    try:
        from tools.telegram_bot import send_notification
        send_notification(text)
    except Exception as exc:
        print(f"⚠️  Motor Telegram hatası: {exc}")


def notify_position_open(
    symbol: str,
    side: str,
    leverage: int,
    entry_price: float,
    margin_usdt: float,
    source: str,
) -> None:
    coin = _coin(symbol)
    src = str(source or "HT").upper()
    if src not in ("HT", "MZ", "MANUEL"):
        src = "HT"
    _send(
        f"📈 POZİSYON AÇILDI\n"
        f"{coin} {side} {int(leverage)}x\n"
        f"Giriş: {_fmt_price(entry_price)}\n"
        f"Marjin: {_fmt_usdt(margin_usdt, signed=False)} USDT\n"
        f"Kaynak: {src}"
    )


def notify_tp1(symbol: str, pnl_pct: float, pnl_usdt: float) -> None:
    _send(
        f"✅ TP1 ALINDI\n"
        f"{_coin(symbol)} {_fmt_pct(pnl_pct)}%\n"
        f"Kâr: {_fmt_usdt(pnl_usdt)} USDT"
    )


def notify_tp2(symbol: str, pnl_pct: float, pnl_usdt: float) -> None:
    _send(
        f"✅ TP2 ALINDI\n"
        f"{_coin(symbol)} {_fmt_pct(pnl_pct)}%\n"
        f"Kâr: {_fmt_usdt(pnl_usdt)} USDT"
    )


def notify_trailing_closed(symbol: str, net_pnl_usdt: float) -> None:
    _send(
        f"🎯 TRAİLİNG KAPANDI\n"
        f"{_coin(symbol)}\n"
        f"Net kâr: {_fmt_usdt(net_pnl_usdt)} USDT"
    )


def notify_d1(symbol: str) -> None:
    _send(
        f"🛡️ SAVUNMA D1\n"
        f"{_coin(symbol)} -%5\n"
        f"Ekleme yapıldı"
    )


def notify_d2(symbol: str) -> None:
    _send(
        f"🛡️ SAVUNMA D2\n"
        f"{_coin(symbol)} -%12\n"
        f"TP donduruldu"
    )


def notify_hard_stop(symbol: str, loss_usdt: float) -> None:
    _send(
        f"🚨 HARD STOP\n"
        f"{_coin(symbol)}\n"
        f"Zarar: -{_fmt_usdt(abs(loss_usdt), signed=False)} USDT"
    )


def notify_time_stop(symbol: str, pnl_usdt: Optional[float] = None) -> None:
    extra = ""
    if pnl_usdt is not None:
        extra = f"\nPnL: {_fmt_usdt(pnl_usdt)} USDT"
    _send(
        f"⏰ ZAMAN STOPU\n"
        f"{_coin(symbol)}\n"
        f"Breakeven kapandı{extra}"
    )
