# -*- coding: utf-8 -*-
"""Haluk Hoca Telegram mesaj arşivi — Claude analiz, DERR kayıt, bildirim."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "mina_trading_journal.db")
MODEL = os.getenv("HALUK_ARCHIVE_MODEL", "claude-sonnet-4-6")

TYPE_LABELS = {
    "sinyal": "Sinyal",
    "kutu": "Kutu",
    "makro": "Makro",
    "haber": "Haber",
    "diger": "Diğer",
}

_claude = None
_claude_lock = threading.Lock()


def _journal():
    from mina_trading_journal import TradingJournal
    return TradingJournal(db_path=DB_PATH)


def _get_claude():
    global _claude
    with _claude_lock:
        if _claude is None:
            import anthropic
            _claude = anthropic.Anthropic()
        return _claude


def _parse_claude_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _heuristic_analysis(raw_text: str) -> Dict[str, Any]:
    upper = raw_text.upper()
    msg_type = "diger"
    if re.search(r"\b(LONG|SHORT|AŞAĞIDAN LONG|YUKARIDAN SHORT)\b", upper):
        msg_type = "sinyal"
    elif any(k in upper for k in ("KUTU", "DESTEK", "DİRENÇ", "DIRENC", "BÖLGE", "RETEST")):
        msg_type = "kutu"
    elif any(k in upper for k in ("TOTAL", "OTHERS", "BTC.D", "ALTLAR", "MAKRO")):
        msg_type = "makro"
    elif any(k in upper for k in ("HABER", "BORSa", "SEC", "FED", "ETF")):
        msg_type = "haber"

    direction = "None"
    if re.search(r"\b(LONG|AL|ALIŞ|ALINIR)\b", upper):
        direction = "AL"
    elif re.search(r"\b(SHORT|SAT|SATIŞ|SATILIR)\b", upper):
        direction = "SAT"

    coins = re.findall(r"\b([A-Z]{2,12})(?:USDT)?\b", upper)
    coins = list(dict.fromkeys(c for c in coins if c not in ("HTTP", "HTTPS", "YOUTU", "LIVE", "RISK")))

    levels = re.findall(r"\d[\d.,]*(?:%|T|B|K|\$)?", raw_text[:400])
    return {
        "message_type": msg_type,
        "coins_mentioned": coins[:8],
        "direction": direction,
        "price_levels": levels[:6],
        "analysis_summary": raw_text[:160].replace("\n", " "),
    }


def analyze_message(raw_text: str) -> Dict[str, Any]:
    if not raw_text.strip():
        return _heuristic_analysis("")
    try:
        client = _get_claude()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    "Haluk Hoca kripto Telegram mesajını analiz et. Sadece JSON döndür:\n"
                    '{"message_type":"sinyal|kutu|makro|haber|diger",'
                    '"coins_mentioned":["BTC","SOL"],'
                    '"direction":"AL|SAT|None",'
                    '"price_levels":["96000","195B"],'
                    '"analysis_summary":"1-2 cümle Türkçe özet"}\n\n'
                    f"Mesaj:\n{raw_text[:2000]}"
                ),
            }],
        )
        data = _parse_claude_json(resp.content[0].text)
        msg_type = str(data.get("message_type") or "diger").lower()
        if msg_type not in TYPE_LABELS:
            msg_type = "diger"
        direction = str(data.get("direction") or "None").upper()
        if direction not in ("AL", "SAT", "NONE"):
            direction = "None"
        if direction == "NONE":
            direction = "None"
        return {
            "message_type": msg_type,
            "coins_mentioned": [str(c).upper().replace("USDT", "") for c in (data.get("coins_mentioned") or [])][:12],
            "direction": direction,
            "price_levels": data.get("price_levels") or [],
            "analysis_summary": str(data.get("analysis_summary") or "")[:500],
        }
    except Exception as exc:
        print(f"[HALUK ARCHIVE] Claude hatası, heuristik kullanılıyor: {exc}")
        return _heuristic_analysis(raw_text)


def send_haluk_telegram(
    message_type: str,
    coins: List[str],
    summary: str,
    price_levels: Optional[List] = None,
) -> bool:
    try:
        from mina_dashboard_settings import load_settings
        if not load_settings().get("telegramNotify", True):
            return False
    except ImportError:
        pass

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    tip = TYPE_LABELS.get(message_type, message_type)
    coin_str = ", ".join(coins[:5]) if coins else "—"
    seviye = ", ".join(str(x) for x in (price_levels or [])[:4]) if price_levels else "—"
    text = (
        "📊 HALUK HOCA\n"
        f"Tip: {tip}\n"
        f"Coin: {coin_str}\n"
        f"Özet: {summary or '—'}\n"
        f"Seviye: {seviye}"
    )
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        return True
    except Exception as exc:
        print(f"[HALUK ARCHIVE] Telegram hatası: {exc}")
        return False


def archive_haluk_message(
    raw_text: str,
    message_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    *,
    notify: bool = True,
    use_claude: bool = True,
) -> int:
    """DERR haluk_messages tablosuna kaydet; isteğe bağlı Telegram bildir."""
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return -1

    ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    journal = _journal()
    try:
        if message_id is not None and journal.haluk_message_exists(message_id):
            return 0

        analysis = analyze_message(raw_text) if use_claude else _heuristic_analysis(raw_text)
        row_id = journal.insert_haluk_message(
            timestamp=ts,
            message_id=message_id,
            raw_text=raw_text,
            message_type=analysis["message_type"],
            coins_mentioned=analysis["coins_mentioned"],
            direction=analysis["direction"],
            price_levels=analysis["price_levels"],
            analysis_summary=analysis["analysis_summary"],
        )
        if row_id > 0 and notify:
            send_haluk_telegram(
                analysis["message_type"],
                analysis["coins_mentioned"],
                analysis["analysis_summary"],
                analysis["price_levels"],
            )
        return row_id
    finally:
        journal.close()


def archive_haluk_message_async(
    raw_text: str,
    message_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    *,
    notify: bool = True,
) -> None:
    threading.Thread(
        target=archive_haluk_message,
        kwargs={
            "raw_text": raw_text,
            "message_id": message_id,
            "timestamp": timestamp,
            "notify": notify,
            "use_claude": True,
        },
        daemon=True,
    ).start()


def query_upbit_listings(limit: int = 300) -> Dict[str, Any]:
    """Upbit / listing / listeleme geçen Haluk mesajları."""
    journal = _journal()
    try:
        cur = journal.conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, raw_text, coins_mentioned, analysis_summary
            FROM haluk_messages
            WHERE lower(raw_text) LIKE '%upbit%'
               OR lower(raw_text) LIKE '%listing%'
               OR lower(raw_text) LIKE '%listeleme%'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        items: List[Dict[str, Any]] = []
        coin_latest: Dict[str, str] = {}
        skip = {
            "UPBIT", "LISTING", "LISTELEME", "THE", "AND", "FOR", "USD", "USDT",
            "KRW", "BTC", "ETH", "API", "NEW", "NOW",
        }
        for row in cur.fetchall():
            raw = row["raw_text"] or ""
            ts = row["timestamp"] or ""
            try:
                coins_json = json.loads(row["coins_mentioned"] or "[]")
            except json.JSONDecodeError:
                coins_json = []
            extra = re.findall(r"\b([A-Z]{2,12})USDT\b", raw.upper())
            extra += re.findall(r"\b([A-Z]{2,12})\b", raw.upper())
            coins = list(dict.fromkeys(
                [str(c).upper().replace("USDT", "") for c in coins_json]
                + [c for c in extra if c not in skip and len(c) >= 2]
            ))
            coins = [c for c in coins if c not in skip][:8]
            items.append({
                "id": row["id"],
                "timestamp": ts,
                "coins": coins,
                "summary": (row["analysis_summary"] or raw[:200]).strip(),
                "snippet": raw[:280].replace("\n", " "),
            })
            for c in coins:
                if c not in coin_latest:
                    coin_latest[c] = ts
        coins_sorted = sorted(
            [{"coin": c, "listedAt": coin_latest[c]} for c in coin_latest],
            key=lambda x: x["listedAt"] or "",
            reverse=True,
        )
        return {"total": len(items), "items": items, "coins": coins_sorted}
    finally:
        journal.close()


def query_haluk_messages(
    coin: Optional[str] = None,
    message_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    journal = _journal()
    try:
        return journal.list_haluk_messages(
            coin=coin,
            message_type=message_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    finally:
        journal.close()
