# -*- coding: utf-8 -*-
"""
Upbit listeleme SHORT trader — ana motordan tamamen izole.
Sabit 10 USDT marjin, 8x izole, stopsuz (likidasyon max kayıp).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(ROOT, "signal_bot", "upbit_listing_trader_state.json")

SIGNAL_SOURCE = "UPBIT_LISTING"
MARGIN_USDT = float(os.environ.get("UPBIT_TRADER_MARGIN_USDT", "10"))
LEVERAGE = int(os.environ.get("UPBIT_TRADER_LEVERAGE", "8"))
PULLBACK_PCT = float(os.environ.get("UPBIT_TRADER_PULLBACK_PCT", "3"))
PEAK_TRACK_SEC = int(os.environ.get("UPBIT_TRADER_PEAK_SEC", "300"))
PEAK_POLL_SEC = int(os.environ.get("UPBIT_TRADER_PEAK_POLL_SEC", "30"))
FUNDING_HOURLY_MIN = float(os.environ.get("UPBIT_TRADER_FUNDING_HOURLY_MIN", "-1"))
PENDING_MAX_SEC = int(os.environ.get("UPBIT_TRADER_PENDING_MAX_SEC", "3600"))

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


def load_state() -> Dict[str, Any]:
    return _read_json(STATE_PATH, {"pending": {}, "active": {}})


def save_state(data: Dict[str, Any]) -> None:
    data["updatedAt"] = int(time.time())
    _write_json(STATE_PATH, data)


def fmt_now() -> str:
    return datetime.now(tz=TR_TZ).strftime("%Y-%m-%d %H:%M")


def _client():
    from backend.config import BinanceConfig
    return BinanceConfig().get_client()


def _journal():
    from mina_trading_journal import TradingJournal
    db = os.path.join(ROOT, "mina_trading_journal.db")
    return TradingJournal(db_path=db)


def telegram_send(text: str) -> bool:
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
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        return True
    except Exception as exc:
        print(f"[UPBIT TRADER] Telegram hatası: {exc}")
        return False


def parse_coins(coin_field: str) -> List[str]:
    if not coin_field or coin_field.strip() in ("—", "-"):
        return []
    parts = re.split(r"[,;/\s]+", coin_field.upper())
    skip = {"UPBIT", "KRW", "BTC", "USDT", "THE", "AND", "FOR", "NEW", "RT"}
    out: List[str] = []
    for p in parts:
        p = re.sub(r"USDT$", "", p.strip())
        if 2 <= len(p) <= 12 and p.isalnum() and p not in skip and p not in out:
            out.append(p)
    return out


def _lot_precision(client, symbol: str) -> int:
    info = client.futures_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            for f in s.get("filters", []):
                if f.get("filterType") == "LOT_SIZE":
                    step = str(f.get("stepSize", "1")).rstrip("0")
                    if "." in step:
                        return len(step.split(".")[-1])
                    return 0
    return 3


def _price_precision(client, symbol: str) -> int:
    info = client.futures_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            for f in s.get("filters", []):
                if f.get("filterType") == "PRICE_FILTER":
                    tick = str(f.get("tickSize", "0.01")).rstrip("0")
                    if "." in tick:
                        return len(tick.split(".")[-1])
                    return 0
    return 4


def _symbol_trading(client, symbol: str) -> bool:
    info = client.futures_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            return s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL"
    return False


def fetch_mark_price(client, symbol: str) -> Optional[float]:
    try:
        r = client.futures_mark_price(symbol=symbol)
        return float(r.get("markPrice") or 0)
    except Exception:
        try:
            return float(client.futures_symbol_ticker(symbol=symbol)["price"])
        except Exception:
            return None


def hourly_funding_pct(client, symbol: str) -> Optional[float]:
    """8 saatlik funding → yaklaşık saatlik %."""
    try:
        rows = client.futures_funding_rate(symbol=symbol, limit=1)
        if not rows:
            mp = client.futures_mark_price(symbol=symbol)
            rate = float(mp.get("lastFundingRate") or 0)
        else:
            rate = float(rows[0].get("fundingRate") or 0)
        return rate * 100.0 / 8.0
    except Exception as exc:
        print(f"[UPBIT TRADER] Funding okunamadı {symbol}: {exc}")
        return None


def has_open_derr_trade(coin: str) -> bool:
    sym = f"{coin}USDT"
    j = _journal()
    try:
        cur = j.conn.cursor()
        cur.execute(
            """
            SELECT id FROM trades
            WHERE symbol=? AND side='SHORT' AND status='open'
              AND signal_source=?
            LIMIT 1
            """,
            (sym, SIGNAL_SOURCE),
        )
        return cur.fetchone() is not None
    finally:
        j.close()


def tracked_keys(state: Optional[Dict[str, Any]] = None) -> Set[str]:
    st = state or load_state()
    keys: Set[str] = set()
    for coin in list(st.get("pending", {}).keys()) + list(st.get("active", {}).keys()):
        keys.add(f"{coin}USDT_SHORT")
    j = _journal()
    try:
        cur = j.conn.cursor()
        cur.execute(
            "SELECT symbol FROM trades WHERE status='open' AND signal_source=? AND side='SHORT'",
            (SIGNAL_SOURCE,),
        )
        for row in cur.fetchall():
            keys.add(f"{row['symbol']}_SHORT")
    except Exception:
        pass
    finally:
        j.close()
    return keys


def is_upbit_listing_position(symbol: str, side: str) -> bool:
    if (side or "").upper() != "SHORT":
        return False
    coin = symbol.replace("USDT", "")
    st = load_state()
    if coin in st.get("pending", {}) or coin in st.get("active", {}):
        return True
    return f"{symbol}_SHORT" in tracked_keys(st)


def on_new_listings(alerts: List[Dict[str, Any]]) -> None:
    if not alerts:
        return
    state = load_state()
    pending = state.setdefault("pending", {})
    now = time.time()

    for alert in alerts:
        for coin in parse_coins(str(alert.get("coin") or "")):
            if coin in pending or coin in state.get("active", {}):
                continue
            if has_open_derr_trade(coin):
                continue
            symbol = f"{coin}USDT"
            try:
                client = _client()
            except Exception as exc:
                print(f"[UPBIT TRADER] Binance client yok: {exc}")
                return
            if not _symbol_trading(client, symbol):
                print(f"[UPBIT TRADER] {symbol} Futures'ta yok — atlandı")
                continue
            price = fetch_mark_price(client, symbol)
            if not price or price <= 0:
                print(f"[UPBIT TRADER] {symbol} fiyat alınamadı")
                continue
            pending[coin] = {
                "coin": coin,
                "symbol": symbol,
                "listing_price": price,
                "peak": price,
                "peak_frozen": False,
                "started_at": now,
                "peak_until": now + PEAK_TRACK_SEC,
                "last_poll": 0.0,
                "source": alert.get("source", "Upbit"),
            }
            print(
                f"[UPBIT TRADER] İzlemeye alındı {coin} listing={price:.6g} "
                f"(5dk zirve taraması)"
            )
            telegram_send(
                "👁️ UPBİT İZLENİYOR\n"
                f"Coin: {coin}\n"
                f"Listeleme fiyatı: {price:.6g}\n"
                f"Zirve bekleniyor...\n"
                f"Saat: {fmt_now()}"
            )
    save_state(state)


def _open_short(client, symbol: str, listing_price: float, peak: float) -> Optional[Dict[str, Any]]:
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception as exc:
        if "-4046" not in str(exc):
            print(f"[UPBIT TRADER] margin type {symbol}: {exc}")
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception as exc:
        print(f"[UPBIT TRADER] leverage {symbol}: {exc}")

    price = fetch_mark_price(client, symbol)
    if not price:
        return None

    prec = _lot_precision(client, symbol)
    qty = round((MARGIN_USDT * LEVERAGE) / price, prec)
    if qty <= 0:
        return None

    order = client.futures_create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=ORDER_TYPE_MARKET,
        quantity=qty,
        positionSide="SHORT",
    )
    entry = price
    pp = _price_precision(client, symbol)
    tp_price = round(listing_price, pp)

    tp_ok = False
    try:
        client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type="TAKE_PROFIT_MARKET",
            stopPrice=tp_price,
            closePosition=True,
            positionSide="SHORT",
            workingType="MARK_PRICE",
        )
        tp_ok = True
    except Exception as exc:
        print(f"[UPBIT TRADER] TP emri atlanamadı (manuel izleme): {exc}")

    j = _journal()
    try:
        trade_id = j.log_trade_open(
            symbol=symbol,
            side="SHORT",
            leverage=LEVERAGE,
            entry_price=entry,
            qty=qty,
            initial_margin=MARGIN_USDT,
            signal_source=SIGNAL_SOURCE,
        )
    finally:
        j.close()

    return {
        "symbol": symbol,
        "entry_price": entry,
        "qty": qty,
        "trade_id": trade_id,
        "tp_price": tp_price,
        "tp_order": tp_ok,
        "peak": peak,
        "listing_price": listing_price,
        "order_id": order.get("orderId"),
    }


def _close_short_market(client, symbol: str, qty: float) -> Optional[float]:
    price = fetch_mark_price(client, symbol)
    prec = _lot_precision(client, symbol)
    try:
        client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=round(qty, prec),
            positionSide="SHORT",
        )
    except Exception as exc:
        print(f"[UPBIT TRADER] Kapatma hatası {symbol}: {exc}")
        return None
    return price


def _binance_short_qty(client, symbol: str) -> float:
    for p in client.futures_position_information(symbol=symbol):
        if p.get("positionSide") == "SHORT":
            return abs(float(p.get("positionAmt") or 0))
    return 0.0


def _process_pending(state: Dict[str, Any]) -> None:
    pending: Dict[str, Any] = state.get("pending") or {}
    if not pending:
        return
    try:
        client = _client()
    except Exception:
        return

    now = time.time()
    done: List[str] = []

    for coin, row in list(pending.items()):
        if now - float(row.get("started_at") or now) > PENDING_MAX_SEC:
            print(f"[UPBIT TRADER] {coin} pending zaman aşımı")
            done.append(coin)
            continue

        if now - float(row.get("last_poll") or 0) < PEAK_POLL_SEC:
            continue

        symbol = row["symbol"]
        price = fetch_mark_price(client, symbol)
        if not price:
            continue
        row["last_poll"] = now

        if not row.get("peak_frozen") and now <= float(row.get("peak_until") or 0):
            row["peak"] = max(float(row.get("peak") or price), price)
        elif not row.get("peak_frozen"):
            row["peak_frozen"] = True
            print(f"[UPBIT TRADER] {coin} zirve donduruldu: {row['peak']:.6g}")

        peak = float(row.get("peak") or price)
        pullback_level = peak * (1 - PULLBACK_PCT / 100.0)
        if price > pullback_level:
            continue

        hourly = hourly_funding_pct(client, symbol)
        if hourly is not None and hourly < FUNDING_HOURLY_MIN:
            telegram_send(
                "⚠️ UPBIT TRADER — Funding filtresi\n"
                f"Coin: {coin}\n"
                f"Saatlik funding: {hourly:.2f}% (limit {FUNDING_HOURLY_MIN:.1f}%)\n"
                "SHORT açılmadı."
            )
            print(f"[UPBIT TRADER] {coin} funding filtresi: {hourly:.2f}%")
            done.append(coin)
            continue

        listing_price = float(row.get("listing_price") or price)
        opened = _open_short(client, symbol, listing_price, peak)
        if not opened:
            continue

        state.setdefault("active", {})[coin] = {
            **opened,
            "coin": coin,
            "opened_at": now,
            "listing_price": listing_price,
        }
        done.append(coin)

        telegram_send(
            "🔔 UPBIT SHORT AÇILDI\n"
            f"Coin: {coin}\n"
            f"Giriş: {opened['entry_price']:.6g}\n"
            f"Zirve: {peak:.6g}\n"
            f"TP (listeleme): {opened['tp_price']:.6g}\n"
            f"Marjin: {MARGIN_USDT:.0f} USDT | {LEVERAGE}x izole\n"
            f"Saat: {fmt_now()}"
        )
        print(f"[UPBIT TRADER] SHORT açıldı {coin} id={opened['trade_id']}")

    for coin in done:
        pending.pop(coin, None)


def _process_active(state: Dict[str, Any]) -> None:
    active: Dict[str, Any] = state.get("active") or {}
    if not active:
        return
    try:
        client = _client()
    except Exception:
        return

    closed: List[str] = []
    for coin, row in list(active.items()):
        symbol = row["symbol"]
        qty = _binance_short_qty(client, symbol)
        mark = fetch_mark_price(client, symbol)
        listing_price = float(row.get("listing_price") or row.get("tp_price") or 0)
        trade_id = int(row.get("trade_id") or 0)

        if qty <= 0:
            close_px = mark or float(row.get("entry_price") or 0)
            entry = float(row.get("entry_price") or close_px)
            pnl = (entry - close_px) * float(row.get("qty") or 0)
            roe = (pnl / MARGIN_USDT * 100) if MARGIN_USDT else 0
            reason = "Likidasyon/Kapanış"
            if mark and listing_price and mark <= listing_price * 1.002:
                reason = "TP (listeleme fiyatı)"

            j = _journal()
            try:
                if trade_id > 0:
                    j.log_trade_close(
                        trade_id,
                        close_px,
                        float(row.get("qty") or 0),
                        reason,
                        pnl,
                        ((entry - close_px) / entry * 100) if entry else 0,
                        roe,
                    )
            finally:
                j.close()

            telegram_send(
                "✅ UPBIT SHORT KAPANDI\n"
                f"Coin: {coin}\n"
                f"Sebep: {reason}\n"
                f"PnL: {pnl:+.2f} USDT\n"
                f"Saat: {fmt_now()}"
            )
            closed.append(coin)
            continue

        if mark and listing_price > 0 and mark <= listing_price and not row.get("tp_order"):
            px = _close_short_market(client, symbol, qty)
            if px is None:
                continue
            entry = float(row.get("entry_price") or px)
            pnl = (entry - px) * qty
            roe = (pnl / MARGIN_USDT * 100) if MARGIN_USDT else 0
            j = _journal()
            try:
                if trade_id > 0:
                    j.log_trade_close(
                        trade_id, px, qty, "TP (listeleme fiyatı)",
                        pnl, ((entry - px) / entry * 100) if entry else 0, roe,
                    )
            finally:
                j.close()
            telegram_send(
                "✅ UPBIT SHORT KAPANDI\n"
                f"Coin: {coin}\n"
                f"Sebep: TP (listeleme fiyatı)\n"
                f"PnL: {pnl:+.2f} USDT\n"
                f"Saat: {fmt_now()}"
            )
            closed.append(coin)

    for coin in closed:
        active.pop(coin, None)


def trader_cycle() -> None:
    state = load_state()
    _process_pending(state)
    _process_active(state)
    save_state(state)


def handle_listing_alerts(alerts: List[Dict[str, Any]]) -> None:
    """Yeni listeleme uyarılarından trader pipeline başlat."""
    on_new_listings(alerts)
    trader_cycle()


def _fmt_ts(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=TR_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def get_dashboard_status() -> Dict[str, Any]:
    """Dashboard Haber sekmesi — izleme, aktif pozisyon, DERR geçmişi."""
    state = load_state()
    pending = []
    for coin, p in (state.get("pending") or {}).items():
        pending.append({
            "coin": coin,
            "symbol": p.get("symbol", f"{coin}USDT"),
            "listing_price": p.get("listing_price"),
            "peak": p.get("peak"),
            "peak_frozen": bool(p.get("peak_frozen")),
            "started_at": p.get("started_at"),
            "started_at_display": _fmt_ts(p.get("started_at")),
        })
    active = []
    for coin, a in (state.get("active") or {}).items():
        active.append({
            "coin": coin,
            "symbol": a.get("symbol", f"{coin}USDT"),
            "entry_price": a.get("entry_price"),
            "listing_price": a.get("listing_price"),
            "tp_price": a.get("tp_price"),
            "peak": a.get("peak"),
            "trade_id": a.get("trade_id"),
        })

    recent_trades: List[Dict[str, Any]] = []
    summary = {
        "total_pnl": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "closed_count": 0,
        "watch_count": len(pending),
        "active_count": len(active),
    }
    j = _journal()
    try:
        cur = j.conn.cursor()
        cur.execute(
            """
            SELECT id, symbol, side, leverage, open_time, close_time,
                   open_price, close_price, pnl_usdt, pnl_percent, roe_percent,
                   status, close_reason
            FROM trades
            WHERE signal_source=?
            ORDER BY COALESCE(close_time, open_time) DESC
            LIMIT 10
            """,
            (SIGNAL_SOURCE,),
        )
        for row in cur.fetchall():
            d = dict(row)
            recent_trades.append({
                "id": d["id"],
                "symbol": d["symbol"],
                "coin": (d["symbol"] or "").replace("USDT", ""),
                "side": d["side"],
                "leverage": d["leverage"],
                "open_time": d["open_time"],
                "close_time": d["close_time"],
                "open_price": d["open_price"],
                "close_price": d["close_price"],
                "pnl_usdt": d["pnl_usdt"],
                "pnl_percent": d["pnl_percent"],
                "roe_percent": d["roe_percent"],
                "status": d["status"],
                "close_reason": d.get("close_reason"),
            })
        cur.execute(
            "SELECT pnl_usdt, status FROM trades WHERE signal_source=?",
            (SIGNAL_SOURCE,),
        )
        for row in cur.fetchall():
            if row["status"] != "closed" or row["pnl_usdt"] is None:
                continue
            pnl = float(row["pnl_usdt"])
            summary["total_pnl"] += pnl
            summary["closed_count"] += 1
            if pnl >= 0:
                summary["win_count"] += 1
            else:
                summary["loss_count"] += 1
    except Exception as exc:
        print(f"[UPBIT TRADER] dashboard status DERR: {exc}")
    finally:
        j.close()

    return {
        "pending": pending,
        "active": active,
        "recent_trades": recent_trades,
        "summary": summary,
        "updated_at": fmt_now(),
    }
