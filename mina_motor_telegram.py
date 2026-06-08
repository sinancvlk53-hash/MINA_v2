# -*- coding: utf-8 -*-
"""Gerçek motor olayları — Telegram bildirim şablonları."""

from __future__ import annotations

from typing import Optional


def _sym(symbol: str) -> str:
    s = str(symbol or "").upper().replace("/", "")
    return s if s.endswith("USDT") else f"{s}USDT"


def _fmt_usdt(value: float, *, signed: bool = True) -> str:
    if signed:
        return f"{value:+.2f}"
    return f"{abs(value):.2f}"


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
    coin = _sym(symbol).replace("USDT", "")
    src = str(source or "HT").upper()
    if src not in ("HT", "MZ", "MANUEL"):
        src = "HT"
    _send(
        f"📈 POZİSYON AÇILDI\n"
        f"{coin} {side} {int(leverage)}x\n"
        f"Giriş: {entry_price}\n"
        f"Marjin: {margin_usdt:.2f} USDT\n"
        f"Kaynak: {src}"
    )


def notify_tp1(symbol: str, pnl_pct: float = 3.0, pnl_usdt: float = 0.0) -> None:
    pct = abs(float(pnl_pct or 3.0))
    _send(f"✅ {_sym(symbol)} TP1 tetiklendi! +%{pct:.0f} | Kalan: %50")


def notify_tp2(symbol: str, pnl_pct: float = 5.0, pnl_usdt: float = 0.0) -> None:
    pct = abs(float(pnl_pct or 5.0))
    _send(f"✅ {_sym(symbol)} TP2 tetiklendi! +%{pct:.0f} | Trailing başladı")


def notify_trailing_closed(symbol: str, net_pnl_usdt: float) -> None:
    _send(
        f"🏁 {_sym(symbol)} trailing ile kapandı | PnL: {_fmt_usdt(net_pnl_usdt)} USDT"
    )


def notify_d1(symbol: str) -> None:
    _send(f"⚠️ {_sym(symbol)} D1 savunma! Ekleme yapıldı")


def notify_d2(symbol: str) -> None:
    _send(
        f"🔴 {_sym(symbol)} D2 savunma! TP donduruldu, kurtarma emri kondu"
    )


def notify_d3(symbol: str) -> None:
    _send(f"🆘 {_sym(symbol)} D3 savunma! Büyük ekleme yapıldı")


def notify_hard_stop(symbol: str, loss_usdt: float = 0.0) -> None:
    _send(
        f"💀 {_sym(symbol)} Hard Stop! Pozisyon kapatıldı | 2 saat cooldown"
    )


def notify_stop_loss(symbol: str, pnl_usdt: float = 0.0) -> None:
    _send(f"🛑 {_sym(symbol)} Stop-Loss tetiklendi | PnL: {_fmt_usdt(pnl_usdt)} USDT")


def notify_manual_stop(symbol: str) -> None:
    _send(f"🔶 {_sym(symbol)} Manuel Stop tetiklendi")


def notify_manual_tp(symbol: str) -> None:
    _send(f"🔶 {_sym(symbol)} Manuel TP tetiklendi")


def notify_merter_dca_open(
    signal_source: str,
    symbol: str,
    parts_filled: int,
    parts_total: int = 10,
) -> None:
    src = str(signal_source or "EI")
    label = "EI" if "ei" in src.lower() else src.replace("merter_", "").upper()
    _send(
        f"🟢 Merter {label}: {_sym(symbol)} açıldı | {parts_filled}/{parts_total} parça"
    )


def notify_merter_tp1(symbol: str, pnl_pct: float = 3.0) -> None:
    pct = abs(float(pnl_pct or 3.0))
    _send(f"✅ Merter {_sym(symbol)} TP1 | +%{pct:.0f}")


def notify_merter_time_stop(symbol: str) -> None:
    _send(f"⏰ Merter {_sym(symbol)} zaman stopu | Breakeven modu")


def notify_time_stop(symbol: str, pnl_usdt: Optional[float] = None) -> None:
    extra = ""
    if pnl_usdt is not None:
        extra = f" | PnL: {_fmt_usdt(pnl_usdt)} USDT"
    _send(f"⏰ {_sym(symbol)} zaman stopu | Breakeven kapandı{extra}")


def notify_system_alert(kind: str, detail: str) -> None:
    labels = {
        "rate_limit": "Rate limit",
        "database_lock": "Database lock",
        "service_down": "Servis düşmesi",
    }
    label = labels.get(kind, kind)
    _send(f"⚠️ Sistem uyarısı: {label}\n{detail[:500]}")


def notify_daily_summary(
    *,
    today_pnl: float,
    trade_count: int,
    wins: int,
    losses: int,
    balance: float,
) -> None:
    wr = (wins / trade_count * 100) if trade_count > 0 else 0.0
    _send(
        f"📊 GÜNLÜK ÖZET (23:00)\n"
        f"Realize PnL: {_fmt_usdt(today_pnl)} USDT\n"
        f"İşlem: {trade_count} ({wins}W / {losses}L) | Win: %{wr:.0f}\n"
        f"Kasa: {balance:.2f} USDT"
    )
