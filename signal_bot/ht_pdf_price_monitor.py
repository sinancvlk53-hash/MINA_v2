# -*- coding: utf-8 -*-
"""HT PDF sinyal fiyat takibi — baz_fiyat, 1s/4s/24s, TP/Stop sonucu."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "mina_trading_journal.db")
TR_TZ = timezone(timedelta(hours=3))

_EXTRA_COLS = (
    ("baz_fiyat", "REAL"),
    ("fiyat_1s", "REAL"),
    ("fiyat_4s", "REAL"),
    ("fiyat_24s", "REAL"),
    ("result_time", "TEXT"),
)

_INTERVAL_HOURS = {"fiyat_1s": 1, "fiyat_4s": 4, "fiyat_24s": 24}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def init_ht_pdf_price_columns() -> None:
    """ht_pdf_basari_orani tablosuna fiyat kolonları ekle."""
    conn = _conn()
    try:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(ht_pdf_basari_orani)").fetchall()
        }
        for col, typ in _EXTRA_COLS:
            if col not in existing:
                conn.execute(f"ALTER TABLE ht_pdf_basari_orani ADD COLUMN {col} {typ}")
        conn.commit()
    finally:
        conn.close()


def _normalize_symbol(symbol: str) -> str:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return ""
    return sym if sym.endswith("USDT") else f"{sym}USDT"


def fetch_binance_price(symbol: str) -> Optional[float]:
    sym = _normalize_symbol(symbol)
    try:
        from backend.config import BinanceConfig

        client = BinanceConfig().get_client()
        return float(client.futures_symbol_ticker(symbol=sym)["price"])
    except Exception as exc:
        log.debug("client fiyat %s: %s", sym, exc)

    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MINA-ht-pdf-price/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return float(data["price"])
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        log.warning("Binance fiyat alınamadı %s: %s", sym, exc)
        return None


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


def _eval_hit(direction: str, price: float, tp: Optional[float], stop: Optional[float]) -> Optional[str]:
    d = (direction or "").upper()
    if d not in ("LONG", "SHORT") or price <= 0:
        return None
    if d == "LONG":
        if tp is not None and tp > 0 and price >= tp:
            return "tp_hit"
        if stop is not None and stop > 0 and price <= stop:
            return "stop_hit"
    else:
        if tp is not None and tp > 0 and price <= tp:
            return "tp_hit"
        if stop is not None and stop > 0 and price >= stop:
            return "stop_hit"
    return None


def _send_telegram(msg: str) -> None:
    try:
        from tools.telegram_bot import send_notification
        send_notification(msg)
    except Exception as exc:
        log.warning("Telegram bildirimi: %s", exc)


def set_baz_fiyat_for_symbol(symbol: str, direction: str, baz_fiyat: float) -> bool:
    """En güncel açık ht_pdf kaydına baz_fiyat yaz."""
    init_ht_pdf_price_columns()
    sym = _normalize_symbol(symbol)
    direction = (direction or "").upper()
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT id FROM ht_pdf_basari_orani
            WHERE symbol = ? AND direction = ?
              AND status = 'approved' AND (result IS NULL OR result = '')
            ORDER BY id DESC LIMIT 1
            """,
            (sym, direction),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE ht_pdf_basari_orani SET baz_fiyat = ? WHERE id = ?",
            (baz_fiyat, int(row["id"])),
        )
        conn.commit()
        log.info("baz_fiyat %s %s → %.8f (id=%s)", sym, direction, baz_fiyat, row["id"])
        return True
    finally:
        conn.close()


def _pending_signals() -> List[Dict[str, Any]]:
    init_ht_pdf_price_columns()
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT id, symbol, direction, entry_price, tp_price, stop_price,
                   baz_fiyat, fiyat_1s, fiyat_4s, fiyat_24s,
                   result, created_at, open_time
            FROM ht_pdf_basari_orani
            WHERE status = 'approved'
              AND (result IS NULL OR result = '')
            ORDER BY id
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _update_row(row_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [row_id]
    conn = _conn()
    try:
        conn.execute(f"UPDATE ht_pdf_basari_orani SET {cols} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def _format_telegram(row: Dict[str, Any], current: float, result: str) -> str:
    sym = str(row.get("symbol") or "?").replace("USDT", "")
    direction = row.get("direction") or "?"
    entry = row.get("entry_price") or row.get("baz_fiyat") or "?"
    return (
        f"📊 {sym} {direction} | Giriş: {entry} | Şu an: {current} | Sonuç: {result}"
    )


def check_pending_signals() -> int:
    """Bekleyen ht_pdf sinyallerini kontrol et — interval fiyat + TP/Stop."""
    init_ht_pdf_price_columns()
    now = datetime.now(TR_TZ)
    updated = 0

    for row in _pending_signals():
        row_id = int(row["id"])
        symbol = row.get("symbol") or ""
        direction = row.get("direction") or ""
        tp = row.get("tp_price")
        stop = row.get("stop_price")
        created = _parse_created_at(row.get("created_at") or row.get("open_time"))

        price = fetch_binance_price(symbol)
        if price is None:
            continue

        # Interval fiyatları
        if created:
            for col, hours in _INTERVAL_HOURS.items():
                if row.get(col) is not None:
                    continue
                if now >= created + timedelta(hours=hours):
                    _update_row(row_id, **{col: price})

        hit = _eval_hit(direction, price, tp, stop)
        if hit:
            ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            _update_row(
                row_id,
                result=hit,
                result_price=price,
                result_time=ts,
                close_time=ts,
            )
            result_label = hit
            updated += 1
        else:
            result_label = "bekliyor"

        _send_telegram(_format_telegram(row, price, result_label))

    return updated


if __name__ == "__main__":
    n = check_pending_signals()
    print(f"ht_pdf_price_monitor: {n} sinyal sonuçlandı")
