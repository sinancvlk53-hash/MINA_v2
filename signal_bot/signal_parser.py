# -*- coding: utf-8 -*-
"""
MINA v2 — Birleşik Sinyal Parser (Katman 1)

İki Telegram kaynağı + Haluk PDF → RAW_SIGNAL_QUEUE
  - merter          : Merter sinyalleri
  - haluk_telegram  : Haluk Hoca Telegram mesajları
  - haluk_pdf       : haluk_pdf_parser entegrasyonu
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_QUEUE_FILE = os.path.join(SIGNAL_BOT_DIR, "raw_signal_queue.json")

# ── Paylaşılan anayasa ───────────────────────────────────────────────────────
LEVERAGE_5X_BASES = frozenset({"BTC", "ETH", "XAU", "XAG"})
MACRO_FILTER_BASES = frozenset({"TOTAL", "OTHERS", "BRENT", "XCU", "DİĞER", "DIGER"})
UPDATE_TRAP = frozenset({"UPDATE", "RETEST", "DURUM"})
NEWS_ALARM = ("FLASHCRASH", "MAYIN TARLASI", "BALINA SATIŞI", "BALINA SATISI")

COIN_ALIASES = {
    "SOLANA": "SOL",
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "RIPPLE": "XRP",
    "DOGECOIN": "DOGE",
}

PAS_RE = re.compile(
    r"pas\b|şu an değil|su an degil|almam|iptal",
    re.IGNORECASE,
)

# ── Merter regex ─────────────────────────────────────────────────────────────
RE_MERTER_DOLLAR = re.compile(
    r"\$([A-Za-z0-9]+)\s+için\s+(Long|Short)\b",
    re.IGNORECASE,
)
RE_MERTER_SFP = re.compile(
    r"\$([A-Za-z0-9]+)\s+için\s+(Long|Short)\b|\$SFP\s+için\s+(Short|Long)\b",
    re.IGNORECASE,
)
RE_GIRIS_STOP = re.compile(
    r"giriş\s*[:\s]*([\d.,]+).*?stop\s*[:\s]*([\d.,]+)",
    re.IGNORECASE | re.DOTALL,
)
RE_MALIYET = re.compile(
    r"([\d.,]+)\s*maliyet",
    re.IGNORECASE,
)
RE_CIFT_ALIM = re.compile(
    r"([\d.,]+)\s*-\s*([\d.,]+)\s*çift\s*alım",
    re.IGNORECASE,
)
RE_CIFT_SATIM = re.compile(
    r"([\d.,]+)\s*-\s*([\d.,]+)\s*çift\s*satım",
    re.IGNORECASE,
)
RE_SOLANA_CHAT = re.compile(
    r"(\w+)\s+var\.\s*([\d.,]+)\s*maliyet",
    re.IGNORECASE,
)

# ── Haluk telegram regex ─────────────────────────────────────────────────────
RE_HALUK_ENTRY = re.compile(
    r"(?:giriş|giris|entry|giriş\s*bölgesi)\s*[:\s]*([\d.,]+)(?:\s*-\s*([\d.,]+))?",
    re.IGNORECASE,
)
RE_HALUK_STOP = re.compile(
    r"(?:stop|d1|stop\s*seviyesi)\s*[:\s]*([\d.,]+)",
    re.IGNORECASE,
)
RE_HALUK_SIDE = re.compile(r"\b(long|short|alım|alim|satış|satis)\b", re.I)
RE_COIN_TICKER = re.compile(r"\b([A-Z]{2,12})USDT\b", re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_num(val: str) -> Optional[float]:
    if not val:
        return None
    try:
        return float(val.replace(",", ".").strip())
    except ValueError:
        return None


def _mid(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is not None and b is not None:
        return (a + b) / 2
    return a or b


def normalize_symbol(raw: str) -> str:
    token = raw.strip().upper().replace("$", "")
    if token in COIN_ALIASES:
        token = COIN_ALIASES[token]
    token = token.replace("USDT", "")
    if token in MACRO_FILTER_BASES:
        return token.replace("İ", "I")
    return f"{token}USDT"


def leverage_for_symbol(symbol: str) -> int:
    base = symbol.replace("USDT", "").upper()
    return 5 if base in LEVERAGE_5X_BASES else 2


def _norm_upper(text: str) -> str:
    t = text.upper()
    for a, b in (("İ", "I"), ("Ş", "S"), ("Ğ", "G"), ("Ü", "U"), ("Ö", "O"), ("Ç", "C")):
        t = t.replace(a, b)
    return t


def check_news_alarm(text: str) -> Optional[str]:
    upper = _norm_upper(text)
    for kw in NEWS_ALARM:
        if _norm_upper(kw) in upper:
            return kw
    return None


def _update_trap(text: str) -> Optional[str]:
    upper = _norm_upper(text)
    for kw in UPDATE_TRAP:
        if kw in upper:
            return kw
    return None


def _macro_in_text(text: str) -> Optional[str]:
    upper = _norm_upper(text)
    for m in ("TOTAL", "OTHERS", "BRENT", "XCU", "DIGER"):
        if re.search(rf"\b{m}\b", upper):
            return m
    return None


def make_record(
    *,
    source: str,
    symbol: str,
    direction: Optional[str] = None,
    entry_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    leverage: Optional[int] = None,
    status: str = "approved",
    reject_reason: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    sym = normalize_symbol(symbol) if not symbol.endswith("USDT") and symbol not in MACRO_FILTER_BASES else symbol
    if not sym.endswith("USDT") and sym not in MACRO_FILTER_BASES:
        sym = normalize_symbol(sym)
    lev = leverage if leverage is not None else leverage_for_symbol(sym)
    rec: Dict[str, Any] = {
        "source": source,
        "symbol": sym,
        "direction": direction,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "leverage": lev,
        "status": status,
        "reject_reason": reject_reason,
        "timestamp": _now_iso(),
    }
    if tp_price is not None:
        rec["tp_price"] = tp_price
    if raw_text:
        rec["raw_snippet"] = raw_text[:300]
    return rec


def send_pause_telegram(keyword: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[signal_parser] PAUSE — {keyword} (Telegram env yok)")
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": (
                    f"🛑 *MINA Haber Şalteri*\n\n"
                    f"Tetikleyen: `{keyword}`\n"
                    "Sistem *PAUSE* — Mimar manuel onay gerekli."
                ),
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
    except Exception as e:
        print(f"[signal_parser] Telegram hatası: {e}")


# ── KAYNAK 1: Merter ─────────────────────────────────────────────────────────

def parse_merter(text: str) -> List[Dict[str, Any]]:
    """Merter Telegram sinyallerini ayrıştır."""
    text = text.strip()
    if not text:
        return []

    records: List[Dict[str, Any]] = []

    # Sohbet formatı: solana var. 125 maliyet 115-125 çift alım ...
    chat = RE_SOLANA_CHAT.search(text)
    if chat:
        coin_raw, maliyet = chat.group(1), _parse_num(chat.group(2))
        symbol = normalize_symbol(coin_raw)
        direction = "LONG"
        entry = maliyet
        stop = None
        tp = None

        alim = RE_CIFT_ALIM.search(text)
        satim = RE_CIFT_SATIM.search(text)
        if satim:
            tp = _mid(_parse_num(satim.group(1)), _parse_num(satim.group(2)))
        # maliyet = giriş; çift alım = giriş bölgesi (maliyet öncelikli)
        if alim and entry is None:
            entry = _mid(_parse_num(alim.group(1)), _parse_num(alim.group(2)))

        records.append(make_record(
            source="merter",
            symbol=symbol,
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            tp_price=tp,
            status="approved",
            raw_text=text,
        ))
        return records

    # $BTC için Long / $SFP için Short
    dollar = RE_MERTER_DOLLAR.search(text)
    if not dollar:
        return records

    symbol = normalize_symbol(dollar.group(1))
    direction = "LONG" if dollar.group(2).upper() == "LONG" else "SHORT"
    entry = stop = tp = None

    gs = RE_GIRIS_STOP.search(text)
    if gs:
        entry = _parse_num(gs.group(1))
        stop = _parse_num(gs.group(2))
    else:
        m = RE_MALIYET.search(text)
        if m:
            entry = _parse_num(m.group(1))
        alim = RE_CIFT_ALIM.search(text)
        satim = RE_CIFT_SATIM.search(text)
        if alim:
            entry = entry or _mid(_parse_num(alim.group(1)), _parse_num(alim.group(2)))
        if satim:
            tp = _mid(_parse_num(satim.group(1)), _parse_num(satim.group(2)))

    records.append(make_record(
        source="merter",
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        tp_price=tp,
        status="approved",
        raw_text=text,
    ))
    return records


# ── KAYNAK 2: Haluk Telegram ─────────────────────────────────────────────────

def parse_haluk_telegram(text: str) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Haluk Hoca Telegram mesajı.
    Returns: (records, system_pause)
    """
    text = text.strip()
    if not text:
        return [], False

    alarm = check_news_alarm(text)
    if alarm:
        send_pause_telegram(alarm)
        return [make_record(
            source="haluk_telegram",
            symbol="SYSTEM",
            direction=None,
            status="rejected",
            reject_reason=f"haber şalteri: {alarm}",
            raw_text=text,
        )], True

    macro = _macro_in_text(text)
    if macro and not RE_HALUK_ENTRY.search(text) and not RE_HALUK_STOP.search(text):
        sym = "OTHERS" if macro in ("DIGER", "DİĞER") else macro
        return [make_record(
            source="haluk_telegram",
            symbol=sym,
            direction=None,
            status="rejected",
            reject_reason="makro filtre (F1) — işlem açılmaz",
            raw_text=text,
        )], False

    trap = _update_trap(text)
    symbol = "UNKNOWN"
    tm = RE_COIN_TICKER.search(text)
    if tm:
        symbol = tm.group(1).upper() + "USDT"
    elif macro:
        symbol = normalize_symbol(macro)

    if trap:
        return [make_record(
            source="haluk_telegram",
            symbol=symbol,
            direction=None,
            status="rejected",
            reject_reason=f"UPDATE tuzağı ({trap})",
            raw_text=text,
        )], False

    entry_m = RE_HALUK_ENTRY.search(text)
    stop_m = RE_HALUK_STOP.search(text)
    entry = _parse_num(entry_m.group(1)) if entry_m else None
    if entry_m and entry_m.group(2):
        entry = _mid(entry, _parse_num(entry_m.group(2)))
    stop = _parse_num(stop_m.group(1)) if stop_m else None

    has_chart = bool(entry and stop) or bool(
        re.search(r"grafik|kutu|giriş\s*kutusu", text, re.I)
    )
    pas = bool(PAS_RE.search(text))

    if pas and not has_chart:
        return [make_record(
            source="haluk_telegram",
            symbol=symbol,
            direction=None,
            status="rejected",
            reject_reason="Pas — grafik/giriş/stop eksik",
            raw_text=text,
        )], False

    direction = "LONG"
    sm = RE_HALUK_SIDE.search(text)
    if sm and sm.group(1).lower() in ("short", "satış", "satis"):
        direction = "SHORT"

    if not entry and not stop:
        return [], False

    return [make_record(
        source="haluk_telegram",
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        status="approved" if (has_chart or (entry and stop)) else "rejected",
        reject_reason=None if (has_chart or (entry and stop)) else "yetersiz veri",
        raw_text=text,
    )], False


# ── KAYNAK 3: Haluk PDF (haluk_pdf_parser) ───────────────────────────────────

def parse_haluk_pdf_path(pdf_path: str) -> Tuple[List[Dict[str, Any]], bool]:
    """Mevcut haluk_pdf_parser ile entegrasyon."""
    from signal_bot.haluk_pdf_parser import parse_haluk_pdf

    result = parse_haluk_pdf(pdf_path)
    records: List[Dict[str, Any]] = []

    if result.system_pause:
        records.append(make_record(
            source="haluk_pdf",
            symbol="SYSTEM",
            direction=None,
            status="rejected",
            reject_reason=f"haber şalteri: {result.pause_keyword}",
        ))
        return records, True

    for m in result.macro_filters:
        records.append(make_record(
            source="haluk_pdf",
            symbol=m["coin"] if str(m["coin"]).endswith("USDT") else f"{m['coin']}USDT",
            direction=None,
            status="rejected",
            reject_reason="makro filtre (F1) — işlem açılmaz",
            raw_text=m.get("text", "")[:200],
        ))

    for r in result.rejected:
        sym = r.get("coin", "UNKNOWN")
        reason = "UPDATE tuzağı" if r.get("reason") == "update_trap" else r.get("reason", "reddedildi")
        records.append(make_record(
            source="haluk_pdf",
            symbol=sym,
            direction=None,
            status="rejected",
            reject_reason=reason,
            raw_text=r.get("snippet"),
        ))

    for s in result.signals:
        records.append(make_record(
            source="haluk_pdf",
            symbol=s["coin"],
            direction=s.get("side"),
            entry_price=s.get("entry_price"),
            stop_price=s.get("d1_price") or _parse_num(str(s.get("stop", "")).replace("—", "")),
            leverage=s.get("leverage"),
            status="approved" if s.get("status") == "approved" else "rejected",
            reject_reason=None,
        ))

    return records, result.system_pause


# ── RAW SIGNAL QUEUE ─────────────────────────────────────────────────────────

def load_queue() -> Dict[str, Any]:
    if not os.path.exists(RAW_QUEUE_FILE):
        return {"version": 1, "layer": "raw_signal_queue", "entries": []}
    try:
        with open(RAW_QUEUE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if "entries" not in data:
            data["entries"] = []
        return data
    except Exception:
        return {"version": 1, "layer": "raw_signal_queue", "entries": []}


def save_queue(data: Dict[str, Any]) -> str:
    data["updated_at"] = _now_iso()
    os.makedirs(os.path.dirname(RAW_QUEUE_FILE), exist_ok=True)
    with open(RAW_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return RAW_QUEUE_FILE


def enqueue_records(records: List[Dict[str, Any]], append: bool = True) -> str:
    """Kayıtları RAW_SIGNAL_QUEUE'ya yaz."""
    if not records:
        return RAW_QUEUE_FILE
    data = load_queue()
    if append:
        data["entries"].extend(records)
    else:
        data["entries"] = records
    path = save_queue(data)

    approved = [r for r in records if r.get("status") == "approved" and r.get("symbol") != "SYSTEM"]
    if approved:
        legacy = {
            "signals": [
                {
                    "coin": r["symbol"],
                    "side": r["direction"],
                    "entry": str(r.get("entry_price") or "—"),
                    "stop": str(r.get("stop_price") or "—"),
                    "leverage": r.get("leverage"),
                    "leverage_label": f"{r.get('leverage')}x",
                    "d1_price": r.get("stop_price"),
                    "source": r.get("source"),
                }
                for r in approved
            ],
            "source": records[0].get("source", "signal_parser"),
        }
        ht_path = os.path.join(SIGNAL_BOT_DIR, "ht_signals_queue.json")
        with open(ht_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False, indent=2)

    return path


def parse_and_enqueue(text: str, source: str) -> List[Dict[str, Any]]:
    """Kaynak tipine göre parse + kuyruk."""
    source = source.lower()
    pause = False
    if source == "merter":
        records = parse_merter(text)
    elif source in ("haluk", "haluk_telegram", "ht"):
        records, pause = parse_haluk_telegram(text)
    else:
        records = parse_merter(text)
        if not records:
            records, pause = parse_haluk_telegram(text)

    if records:
        enqueue_records(records)
    return records


def parse_pdf_and_enqueue(pdf_path: str) -> List[Dict[str, Any]]:
    records, _ = parse_haluk_pdf_path(pdf_path)
    if records:
        enqueue_records(records)
    return records


# ── TEST ─────────────────────────────────────────────────────────────────────

TEST_MESSAGES = [
    ("merter", "$BTC için Long, giriş 65000, stop 63000"),
    ("merter", "solana var. 125 maliyet 115-125 çift alım 131-135 çift satım"),
    ("haluk_telegram", "BTCUSDT UPDATE: stop seviyesi güncellendi"),
]


def run_tests() -> None:
    print("=" * 60)
    print("SIGNAL_PARSER — TEST ÇIKTILARI")
    print("=" * 60)
    all_records: List[Dict[str, Any]] = []
    for i, (src, msg) in enumerate(TEST_MESSAGES, 1):
        print(f"\n--- TEST {i} [{src}] ---")
        print(f"INPUT: {msg}")
        if src == "merter":
            out = parse_merter(msg)
        else:
            out, pause = parse_haluk_telegram(msg)
            if pause:
                print("SYSTEM_PAUSE: true")
        print("OUTPUT:")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        all_records.extend(out)

    enqueue_records(all_records, append=True)
    print(f"\n--- QUEUE ---\n{RAW_QUEUE_FILE} güncellendi ({len(all_records)} kayıt eklendi)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests()
    elif len(sys.argv) > 2 and sys.argv[1] == "parse":
        src, text = sys.argv[2], " ".join(sys.argv[3:])
        recs = parse_and_enqueue(text, src)
        print(json.dumps(recs, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1].endswith(".pdf"):
        recs = parse_pdf_and_enqueue(sys.argv[1])
        print(json.dumps(recs, ensure_ascii=False, indent=2))
    else:
        run_tests()
