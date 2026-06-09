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


def notify_merter_dca_closed(symbol: str, reason: str, pnl_usdt: float = 0.0) -> None:
    _send(
        f"🔵 Merter DCA kapandı: {_sym(symbol)}\n"
        f"Sebep: {reason}\n"
        f"PnL: {_fmt_usdt(pnl_usdt)} USDT"
    )


def _fmt_price(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value or "—")


def _ht_rr_ratio(entry: float, tp: float, stop: float, side: str) -> str:
    try:
        entry_f, tp_f, stop_f = float(entry), float(tp), float(stop)
        side_u = str(side or "").upper()
        if side_u == "LONG":
            risk = entry_f - stop_f
            reward = tp_f - entry_f
        else:
            risk = stop_f - entry_f
            reward = entry_f - tp_f
        if risk <= 0 or reward <= 0:
            return "—"
        return f"1:{reward / risk:.1f}"
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"


def _ht_source_label(signal: dict, source_info: str = "") -> str:
    src = str(signal.get("source") or source_info or "").upper()
    if "PDF" in src or "HALUK_PDF" in src:
        return "HT PDF"
    if "VISION" in src or "GÖRSEL" in src or "GORSEL" in src:
        return "HT Görsel"
    if "TEXT" in src or "METİN" in src or "METIN" in src:
        return "HT Metin"
    return "HT"


def notify_ht_signal_queued(signal: dict, *, source_info: str = "") -> None:
    """ht_signals_queue.json sinyali — Telegram bildirimi."""
    coin = _sym(signal.get("coin") or signal.get("symbol") or "")
    side = str(signal.get("side") or signal.get("direction") or "").upper()
    entry = signal.get("entry") or signal.get("entry_price")
    tp = signal.get("tp") or signal.get("tp_price") or signal.get("tp1")
    stop = signal.get("stop") or signal.get("stop_price")
    if not all(v not in (None, "", "—") for v in (entry, tp, stop)):
        return

    src_label = _ht_source_label(signal, source_info)
    rr = _ht_rr_ratio(entry, tp, stop, side)
    dir_icon = "📈" if side == "LONG" else "📉"
    _send(
        "🎯 HT SİNYAL\n"
        "━━━━━━━━━━━━━━\n"
        f"📌 COIN: {coin}\n"
        f"{dir_icon} YÖN: {side}\n"
        f"💰 GİRİŞ: {_fmt_price(entry)}\n"
        f"🎯 HEDEF: {_fmt_price(tp)}\n"
        f"🛑 STOP: {_fmt_price(stop)}\n"
        f"📊 R/R: {rr}\n"
        f"⚡ KAYNAK: {src_label}\n"
        "━━━━━━━━━━━━━━\n"
        "✅ Limit emir kuyruğa alındı"
    )


def notify_haluk_signal_opened(
    symbol: str,
    side: str,
    entry_price: float,
    tp1: float,
    tp2: float,
    leverage: int = 4,
) -> None:
    coin = _sym(symbol).replace("USDT", "")
    _send(
        f"✅ Haluk sinyali açıldı: {coin} {side} {leverage}x\n"
        f"Giriş: {entry_price:.4f}\n"
        f"TP1: {tp1:.4f}\n"
        f"TP2: {tp2:.4f}"
    )


def notify_haluk_slot_reject(symbol: str, reason: str = "slot dolu") -> None:
    coin = _sym(symbol).replace("USDT", "")
    r = str(reason or "").lower()
    if "max_positions" in r or "slot" in r or "margin_cap" in r:
        msg = f"⚠️ Haluk sinyali: {coin} — slot dolu, açılamadı"
    elif "kill" in r:
        msg = f"⚠️ Haluk sinyali: {coin} — kill-switch aktif, açılamadı"
    elif "cooldown" in r or "coin_lock" in r or "kilit" in r:
        msg = f"⚠️ Haluk sinyali: {coin} — coin kilitli, açılamadı"
    elif "filtre" in r or "guillotine" in r or "reject" in r:
        msg = f"⚠️ Haluk sinyali: {coin} — filtre reddi, açılamadı"
    else:
        msg = f"⚠️ Haluk sinyali: {coin} — açılamadı ({reason})"
    _send(msg)


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
