# -*- coding: utf-8 -*-
"""
MINA v2 — Merter sinyali: K1 (kuyruk) → K2 (giyotin) → K3 → DERR.

raw_signal_queue.json içindeki Merter kayıtları işlenir;
Haluk TOTAL makro bağlamı kuyruktan okunur.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mina_trading_journal import TradingJournal
from signal_bot.signal_guillotine import (
    evaluate_guillotine,
    evaluate_katman3,
    merter_has_sfp,
    parse_total_direction,
)
from signal_bot.signal_parser import RAW_QUEUE_FILE, load_queue

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_LOG = os.path.join(SIGNAL_BOT_DIR, "pipeline_audit.log")
DEFAULT_DB = os.path.join(_ROOT, "mina_trading_journal.db")


def _utc_session() -> str:
    """UTC saate göre aktif seans adı."""
    h = datetime.now(timezone.utc).hour
    if 0 <= h < 7:
        return "Asya"
    if 7 <= h < 13:
        return "Londra"
    if 13 <= h < 21:
        return "New York"
    return "Asya"


def entry_fingerprint(entry: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(entry.get("timestamp", "")),
            str(entry.get("source", "")),
            str(entry.get("symbol", "")),
            str(entry.get("raw_snippet", entry.get("raw_text", "")))[:120],
        ]
    )


def extract_total_macro_text(queue: Dict[str, Any]) -> str:
    """Kuyruktaki en güncel TOTAL / Haluk makro metni."""
    chunks: List[str] = []

    for mf in queue.get("macro_filters") or []:
        if str(mf.get("coin", "")).upper() == "TOTAL":
            chunks.append(str(mf.get("text", "")))

    entries = queue.get("entries") or []
    for ent in reversed(entries):
        src = str(ent.get("source", "")).lower()
        sym = str(ent.get("symbol", "")).upper()
        snippet = ent.get("raw_snippet") or ent.get("raw_text") or ""
        if sym == "TOTAL" or "TOTAL" in snippet.upper():
            if src.startswith("haluk") or ent.get("reject_reason", "").startswith("makro"):
                chunks.append(snippet)
        elif src.startswith("haluk") and "TOTAL" in snippet.upper():
            chunks.append(snippet)

    return "\n".join(chunks).strip()


def queue_snapshot(queue: Dict[str, Any]) -> Dict[str, Any]:
    entries = queue.get("entries") or []
    merter = [e for e in entries if e.get("source") == "merter"]
    haluk = [e for e in entries if str(e.get("source", "")).startswith("haluk")]
    macro = extract_total_macro_text(queue)
    return {
        "updated_at": queue.get("updated_at"),
        "entries_total": len(entries),
        "merter_count": len(merter),
        "haluk_count": len(haluk),
        "legacy_signals": len(queue.get("signals") or []),
        "rejected_blocks": len(queue.get("rejected") or []),
        "total_macro_chars": len(macro),
        "total_direction": parse_total_direction(macro) if macro else None,
        "last_merter": merter[-1] if merter else None,
    }


def build_k1_report(entry: Dict[str, Any], queue: Dict[str, Any]) -> Dict[str, Any]:
    macro = extract_total_macro_text(queue)
    raw = entry.get("raw_snippet") or entry.get("raw_text") or ""
    return {
        "layer": 1,
        "queue_status": entry.get("status"),
        "reject_reason": entry.get("reject_reason"),
        "symbol": entry.get("symbol"),
        "direction": entry.get("direction"),
        "leverage": entry.get("leverage"),
        "entry_price": entry.get("entry_price"),
        "stop_price": entry.get("stop_price"),
        "timestamp": entry.get("timestamp"),
        "raw_snippet": raw[:300],
        "has_sfp": merter_has_sfp(raw, entry),
        "total_direction_from_queue": parse_total_direction(macro),
        "macro_excerpt": macro[:400] if macro else "(TOTAL makro kuyrukta yok)",
    }


def process_merter_entry(
    entry: Dict[str, Any],
    *,
    queue: Optional[Dict[str, Any]] = None,
    journal: Optional[TradingJournal] = None,
    session: Optional[str] = None,
    scenario_prefix: str = "REAL",
    print_terminal: bool = True,
) -> Dict[str, Any]:
    """Tek Merter kaydı için tam pipeline + DERR."""
    queue = queue or load_queue()
    macro_text = extract_total_macro_text(queue)
    sess = session or _utc_session()
    raw = entry.get("raw_snippet") or entry.get("raw_text") or ""

    k1 = build_k1_report(entry, queue)
    k2 = evaluate_guillotine(
        merter_record=entry,
        haluk_macro_text=macro_text,
        session=sess,
        merter_raw_text=raw,
    )
    k3 = evaluate_katman3(k2)

    ts = (entry.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    ts_short = ts.replace(":", "").replace("-", "")[:15]
    label = f"{scenario_prefix}_{ts_short}_{entry.get('symbol', 'UNK')}"

    derr_id = -1
    own_journal = False
    if journal is None:
        journal = TradingJournal(db_path=DEFAULT_DB)
        own_journal = True

    derr_id = journal.log_signal_decision(
        scenario_label=label,
        merter_symbol=str(entry.get("symbol", "?")),
        merter_direction=str(entry.get("direction", "?")),
        trading_session=sess,
        has_sfp=bool(k1.get("has_sfp")),
        total_direction=k1.get("total_direction_from_queue"),
        k1=k1,
        k2=k2,
        k3=k3,
    )

    if own_journal:
        journal.close()

    result = {
        "fingerprint": entry_fingerprint(entry),
        "scenario_label": label,
        "derr_id": derr_id,
        "session": sess,
        "k1": k1,
        "k2": k2,
        "k3": k3,
    }

    if print_terminal:
        _print_pipeline_result(result, queue)

    _append_audit_log(result)
    return result


def _print_pipeline_result(result: Dict[str, Any], queue: Dict[str, Any]) -> None:
    snap = queue_snapshot(queue)
    print("\n" + "=" * 72, flush=True)
    print("MINA PIPELINE — GERÇEK MERTER KUYRUK KAYDI", flush=True)
    print("=" * 72, flush=True)
    print(f"  Kuyruk: entries={snap['entries_total']} merter={snap['merter_count']} "
          f"updated={snap['updated_at']}", flush=True)
    print(f"  TOTAL yön (kuyruk): {snap['total_direction']}", flush=True)
    print(f"  Seans (UTC): {result['session']}", flush=True)
    print(f"  DERR id: {result['derr_id']}  label: {result['scenario_label']}", flush=True)
    print("\n  [KATMAN 1 — raw_signal_queue kaydı]", flush=True)
    print(json.dumps(result["k1"], ensure_ascii=False, indent=4), flush=True)
    print("\n  [KATMAN 2 — giyotin]", flush=True)
    print(json.dumps(result["k2"], ensure_ascii=False, indent=4), flush=True)
    print("\n  [KATMAN 3 — aksiyon]", flush=True)
    print(json.dumps(result["k3"], ensure_ascii=False, indent=4), flush=True)
    print(f"\n  >>> SONUÇ: {result['k2'].get('label')}  parlaklık={result['k2'].get('brightness')}", flush=True)
    print("=" * 72 + "\n", flush=True)


def _append_audit_log(result: Dict[str, Any]) -> None:
    line = (
        f"[{datetime.now().isoformat()}] "
        f"id={result['derr_id']} {result['scenario_label']} "
        f"label={result['k2'].get('label')} brightness={result['k2'].get('brightness')}\n"
    )
    try:
        with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def print_queue_fragments() -> None:
    """Kuyruk parçalarını terminale özetle."""
    queue = load_queue()
    snap = queue_snapshot(queue)
    print("\n--- raw_signal_queue.json ÖZET ---", flush=True)
    print(json.dumps(snap, ensure_ascii=False, indent=2, default=str), flush=True)
    entries = queue.get("entries") or []
    if entries:
        print(f"\n--- entries[] son {min(5, len(entries))} kayıt ---", flush=True)
        for e in entries[-5:]:
            print(
                f"  [{e.get('timestamp')}] {e.get('source')} {e.get('symbol')} "
                f"{e.get('direction')} status={e.get('status')}",
                flush=True,
            )
