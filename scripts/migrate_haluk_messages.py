#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""signals_log.txt + ht_history.json → haluk_messages tablosuna aktar."""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

SIGNALS_LOG = os.path.join(ROOT, "signal_bot", "signals_log.txt")
HT_HISTORY_JSON = os.path.join(ROOT, "signal_bot", "history", "ht_history.json")
BATCH_SIZE = 10

LOG_PATTERN = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+\[HALUK\]\s+(?:İLK|ILK)\s+MESAJ.*?id=(\d+)\s+\|\s+metin:\s*(.+)$",
    re.IGNORECASE,
)


def load_from_signals_log() -> list[dict]:
    if not os.path.isfile(SIGNALS_LOG):
        return []
    out = []
    with open(SIGNALS_LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LOG_PATTERN.match(line.strip())
            if not m:
                continue
            out.append({
                "timestamp": m.group(1),
                "message_id": int(m.group(2)),
                "raw_text": m.group(3).strip(),
            })
    return out


def load_from_ht_history() -> list[dict]:
    if not os.path.isfile(HT_HISTORY_JSON):
        return []
    data = json.load(open(HT_HISTORY_JSON, encoding="utf-8"))
    out = []
    for row in data:
        text = str(row.get("metin") or "").strip()
        if not text:
            continue
        out.append({
            "timestamp": str(row.get("tarih") or "")[:19].replace("T", " "),
            "message_id": row.get("msg_id"),
            "raw_text": text,
        })
    return out


def merge_messages(*sources: list[dict]) -> list[dict]:
    by_id: dict[int, dict] = {}
    no_id: list[dict] = []
    for src in sources:
        for item in src:
            mid = item.get("message_id")
            if mid is not None:
                by_id[int(mid)] = item
            else:
                no_id.append(item)
    merged = list(by_id.values())
    seen_text = {m["raw_text"] for m in merged}
    for item in no_id:
        if item["raw_text"] not in seen_text:
            merged.append(item)
            seen_text.add(item["raw_text"])
    merged.sort(key=lambda x: x.get("timestamp") or "")
    return merged


def analyze_batch(messages: list[dict]) -> list[dict]:
    from signal_bot.haluk_message_store import analyze_message, _heuristic_analysis

    if not os.getenv("ANTHROPIC_API_KEY"):
        return [_heuristic_analysis(m["raw_text"]) for m in messages]

    import anthropic
    client = anthropic.Anthropic()
    model = os.getenv("HALUK_ARCHIVE_MODEL", "claude-sonnet-4-6")
    numbered = "\n".join(
        f"{i}: {m['raw_text'][:600].replace(chr(10), ' ')}" for i, m in enumerate(messages)
    )
    prompt = (
        "Her Haluk Hoca mesajı için JSON array döndür. Her eleman:\n"
        '{"i":0,"message_type":"sinyal|kutu|makro|haber|diger",'
        '"coins_mentioned":["BTC"],"direction":"AL|SAT|None",'
        '"price_levels":["96000"],"analysis_summary":"1-2 cümle"}\n\n'
        f"Mesajlar:\n{numbered}"
    )
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?", "", raw).strip()
            raw = re.sub(r"```$", "", raw).strip()
        rows = json.loads(raw)
        out = []
        for i, msg in enumerate(messages):
            row = next((r for r in rows if r.get("i") == i), None)
            if row:
                direction = str(row.get("direction") or "None").upper()
                if direction == "NONE":
                    direction = "None"
                out.append({
                    "message_type": str(row.get("message_type") or "diger").lower(),
                    "coins_mentioned": [str(c).upper().replace("USDT", "") for c in (row.get("coins_mentioned") or [])],
                    "direction": direction if direction in ("AL", "SAT") else "None",
                    "price_levels": row.get("price_levels") or [],
                    "analysis_summary": str(row.get("analysis_summary") or "")[:500],
                })
            else:
                out.append(analyze_message(msg["raw_text"]))
        return out
    except Exception as exc:
        print(f"Batch Claude hatası, tekil analiz: {exc}")
        return [analyze_message(m["raw_text"]) for m in messages]


def main() -> None:
    from mina_trading_journal import TradingJournal

    messages = merge_messages(load_from_signals_log(), load_from_ht_history())
    print(f"Toplam kaynak mesaj: {len(messages)}")

    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    journal = TradingJournal(db_path=db_path)
    inserted = skipped = 0

    pending = [m for m in messages if not (
        m.get("message_id") is not None and journal.haluk_message_exists(m.get("message_id"))
    )]
    print(f"Yeni aktarılacak: {len(pending)}")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        print(f"Claude batch {start + 1}-{start + len(batch)} / {len(pending)}", flush=True)
        analyses = analyze_batch(batch)
        for msg, analysis in zip(batch, analyses):
            rid = journal.insert_haluk_message(
                timestamp=msg.get("timestamp") or "",
                message_id=msg.get("message_id"),
                raw_text=msg["raw_text"],
                message_type=analysis["message_type"],
                coins_mentioned=analysis["coins_mentioned"],
                direction=analysis["direction"],
                price_levels=analysis["price_levels"],
                analysis_summary=analysis["analysis_summary"],
            )
            if rid > 0:
                inserted += 1
            else:
                skipped += 1

    journal.close()
    print(f"\nTamamlandı: {inserted} eklendi, {skipped} atlandı (duplicate)")


if __name__ == "__main__":
    main()
