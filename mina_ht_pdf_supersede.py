# -*- coding: utf-8 -*-
"""
Haluk PDF — aynı coin için yeni sinyal gelince eski kuyruk/emir/journal kaydını geçersiz kıl.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
HT_QUEUE_FILE = os.path.join(ROOT, "signal_bot", "ht_signals_queue.json")
PENDING_ORDERS_FILE = os.path.join(ROOT, "pending_orders.json")
JOURNAL_DB = os.path.join(ROOT, "mina_trading_journal.db")


def normalize_ht_symbol(raw: str) -> str:
    sym = str(raw or "").upper().strip()
    if not sym:
        return ""
    if sym.endswith("USDT"):
        return sym
    return sym + "USDT"


def signal_symbol(sig: Dict[str, Any]) -> str:
    return normalize_ht_symbol(sig.get("symbol") or sig.get("coin") or "")


def _log(log: Callable[[str], Any], msg: str) -> None:
    log(msg)


def get_binance_client_optional():
    try:
        from config import BinanceConfig

        return BinanceConfig().get_client()
    except Exception:
        return None


def _load_pending_orders() -> Dict[str, Any]:
    try:
        with open(PENDING_ORDERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_pending_orders(data: Dict[str, Any]) -> None:
    try:
        with open(PENDING_ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def cancel_binance_pending_limits(
    client,
    symbol: str,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """Coin için tüm bekleyen LIMIT emirlerini iptal et."""
    sym = normalize_ht_symbol(symbol)
    if not sym or client is None:
        return []

    cancelled: List[Dict[str, Any]] = []
    try:
        orders = client.futures_get_open_orders(symbol=sym)
    except Exception as exc:
        _log(log, f"[HT_SUPERSEDE] {sym} emir listesi hatası: {exc}")
        return cancelled

    for o in orders:
        if str(o.get("type", "")).upper() != "LIMIT":
            continue
        oid = o.get("orderId")
        try:
            client.futures_cancel_order(symbol=sym, orderId=oid)
            cancelled.append(o)
            _log(
                log,
                f"[HT_SUPERSEDE] Limit iptal {sym} {o.get('side')} "
                f"orderId={oid} price={o.get('price')}",
            )
        except Exception as exc:
            _log(log, f"[HT_SUPERSEDE] Limit iptal hata {sym} #{oid}: {exc}")

    if cancelled:
        pending = _load_pending_orders()
        for pk in list(pending.keys()):
            info = pending.get(pk) or {}
            if info.get("symbol") == sym or str(pk).startswith(f"{sym}_"):
                pending.pop(pk, None)
        _save_pending_orders(pending)

    return cancelled


def cancel_ht_pdf_basari_for_symbol(
    symbol: str,
    *,
    log: Callable[[str], Any] = print,
) -> int:
    """ht_pdf_basari_orani tablosunda coin için aktif kayıtları cancelled yap."""
    sym = normalize_ht_symbol(symbol)
    if not sym:
        return 0
    try:
        from mina_trading_journal import TradingJournal

        journal = TradingJournal(db_path=JOURNAL_DB)
        n = journal.cancel_ht_pdf_basari_for_symbol(sym)
        journal.close()
        if n:
            _log(log, f"[HT_SUPERSEDE] ht_pdf_basari_orani {sym}: {n} kayıt cancelled")
        return n
    except Exception as exc:
        _log(log, f"[HT_SUPERSEDE] journal cancel hata {sym}: {exc}")
        return 0


def supersede_ht_queue_for_symbol(
    symbol: str,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """ht_signals_queue.json içinde aynı coin sinyallerini kaldır."""
    sym = normalize_ht_symbol(symbol)
    if not sym or not os.path.isfile(HT_QUEUE_FILE):
        return []

    try:
        with open(HT_QUEUE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    removed: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for sig in data.get("signals") or []:
        if signal_symbol(sig) == sym:
            old = dict(sig)
            old["status"] = "cancelled"
            old["superseded_at"] = now
            old["superseded_reason"] = "yeni_pdf"
            removed.append(old)
        else:
            kept.append(sig)

    if not removed:
        return []

    data["signals"] = kept
    data["updated_at"] = now
    try:
        with open(HT_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _log(log, f"[HT_SUPERSEDE] ht_signals_queue {sym}: {len(removed)} eski sinyal kaldırıldı")
    except OSError as exc:
        _log(log, f"[HT_SUPERSEDE] ht_signals_queue yazma hata: {exc}")
    return removed


def supersede_ht_pdf_coin(
    symbol: str,
    client=None,
    *,
    log: Callable[[str], Any] = print,
) -> Dict[str, Any]:
    """
    Aynı coin için eski Haluk PDF sinyalini geçersiz kıl:
    kuyruk → Binance limit iptal → ht_pdf_basari_orani cancelled.
    """
    sym = normalize_ht_symbol(symbol)
    if not sym:
        return {"symbol": "", "queue_removed": 0, "limits_cancelled": 0, "journal_cancelled": 0}

    if client is None:
        client = get_binance_client_optional()

    removed = supersede_ht_queue_for_symbol(sym, log=log)
    limits = cancel_binance_pending_limits(client, sym, log=log) if client else []
    journal_n = cancel_ht_pdf_basari_for_symbol(sym, log=log)

    return {
        "symbol": sym,
        "queue_removed": len(removed),
        "limits_cancelled": len(limits),
        "journal_cancelled": journal_n,
    }


def supersede_ht_pdf_coins(
    symbols: List[str],
    client=None,
    *,
    log: Callable[[str], Any] = print,
) -> List[Dict[str, Any]]:
    """Birden fazla coin için supersede (sırayla, kısa gecikme)."""
    if client is None:
        client = get_binance_client_optional()
    seen: set = set()
    results: List[Dict[str, Any]] = []
    for raw in symbols:
        sym = normalize_ht_symbol(raw)
        if not sym or sym in seen:
            continue
        seen.add(sym)
        results.append(supersede_ht_pdf_coin(sym, client, log=log))
        time.sleep(0.15)
    return results
