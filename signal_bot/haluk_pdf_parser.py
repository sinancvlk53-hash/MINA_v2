# -*- coding: utf-8 -*-
"""
Haluk Hoca PDF Otomasyon Modülü — MINA v2 Katman 1 (Sinyal Girişi)

GÖREV 1: PDF metin + tablo ayrıştırma (pdfplumber)
GÖREV 2: Anayasa kuralları (kaldıraç, D1=stop fiyat, makro F1, grafik onayı)
GÖREV 3: UPDATE tuzağı + haber şalteri
GÖREV 4: raw_signal_queue.json (Katman 2 giyotin beslemesi)
"""

from __future__ import annotations

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_QUEUE_FILE = os.path.join(SIGNAL_BOT_DIR, "raw_signal_queue.json")

# ── Anayasa sabitleri ─────────────────────────────────────────────────────
LEVERAGE_5X_COINS = frozenset({"BTC", "ETH", "XAU", "XAG"})
MACRO_FILTER_COINS = frozenset({
    "TOTAL", "OTHERS", "BRENT", "XCU", "TOTAL2", "TOTAL3", "BTC.D", "USDT.D",
})
KNOWN_COINS = (
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "LINK", "LTC", "BCH",
    "XLM", "ZEC", "ETC", "HYPE", "AVAX", "DOT", "TA", "LAB", "US", "XAU", "XAG",
    "TOTAL", "OTHERS", "BRENT", "XCU", "CME", "TOTAL2", "TOTAL3", "BTC.D", "USDT.D",
)

UPDATE_TRAP_KEYWORDS = ("UPDATE", "RETEST", "DURUM")
NEWS_ALARM_KEYWORDS = ("FLASHCRASH", "MAYIN TARLASI", "BALINA SATIŞI", "BALINA SATISI")

PAS_PHRASES = re.compile(
    r"pas\b|şu an değil|su an degil|değil\b|degil\b|almam|iptal|bulaşm",
    re.IGNORECASE,
)
CHART_KEYWORDS_RE = re.compile(
    r"kutu|grafik|giriş\s*kutusu|giris\s*kutusu|entry\s*box|chart",
    re.IGNORECASE,
)
MACRO_SR_SUPPORT_RE = re.compile(
    r"(?:destek|support|alt\s*seviye)\s*[:\-]?\s*([\d.,\s\-–—]+)",
    re.IGNORECASE,
)
MACRO_SR_RESIST_RE = re.compile(
    r"(?:direnç|direnc|resistance|üst\s*seviye|ust\s*seviye)\s*[:\-]?\s*([\d.,\s\-–—]+)",
    re.IGNORECASE,
)
MACRO_LEVELS_FILE = os.path.join(SIGNAL_BOT_DIR, "macro_levels.json")
ENTRY_RE = re.compile(
    r"(?:giriş|giris|entry|giriş\s*bölgesi|giris\s*bolgesi)\s*[:\s]*"
    r"([\d.,]+)\s*(?:-|–|—|to|ile)?\s*([\d.,]*)",
    re.IGNORECASE,
)
STOP_RE = re.compile(
    r"(?:stop|d1|stop\s*seviyesi|kaçış)\s*[:\s]*([\d.,]+)",
    re.IGNORECASE,
)
SIDE_LONG_RE = re.compile(r"\b(long|alım|alim|yukarı|yukari|pozdayız|pozdayiz|devam)\b", re.I)
SIDE_SHORT_RE = re.compile(
    r"\b(short|satış|satis|aşağı|asagi|almam|alinmaz)\b", re.I
)
SECTION_HEADER_RE = re.compile(
    r"^(?:---\s*)?([A-Z]{2,12}(?:\.[A-Z])?)(?:USDT)?\s*(LONG|SHORT)?\s*(?:---)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
BULLET_COIN_RE = re.compile(
    r"^[•\-\*]?\s*([A-Z]{2,12}(?:\.[A-Z])?(?:USDT)?)\s*[:\-]",
    re.MULTILINE | re.IGNORECASE,
)
NOT_COIN_TOKENS = frozenset({
    "STOP", "LONG", "SHORT", "UPDATE", "RETEST", "DURUM", "ENTRY", "GIRIS",
    "GIRIŞ", "PAS", "TP", "SL", "ROI", "ROE", "PDF", "F1",
})


@dataclass
class ParsedSection:
    coin: str
    raw_text: str
    side: Optional[str] = None


@dataclass
class ParseResult:
    system_pause: bool = False
    pause_reason: Optional[str] = None
    pause_keyword: Optional[str] = None
    macro_filters: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    raw_text_length: int = 0
    tables_count: int = 0
    source: str = "HALUK_PDF"
    parsed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── GÖREV 1: PDF extraction ─────────────────────────────────────────────────

def extract_pdf_content(pdf_path: str) -> Tuple[str, List[List[List[str]]]]:
    """Metin ve tabloları pdfplumber ile çeker."""
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("pdfplumber gerekli: pip install pdfplumber") from e

    text_parts: List[str] = []
    all_tables: List[List[List[str]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
            tables = page.extract_tables() or []
            for tbl in tables:
                if tbl:
                    all_tables.append(tbl)

    return "\n\n".join(text_parts), all_tables


def tables_to_text_snippets(tables: List[List[List[str]]]) -> str:
    """Tablo hücrelerini arama için metne çevirir."""
    lines: List[str] = []
    for tbl in tables:
        for row in tbl:
            if not row:
                continue
            cells = [str(c).strip() for c in row if c]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


# ── GÖREV 3: Kill switches ─────────────────────────────────────────────────

def check_news_alarm(full_text: str) -> Optional[Tuple[str, str]]:
    upper = full_text.upper()
    for kw in NEWS_ALARM_KEYWORDS:
        if kw in upper.replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C"):
            return "haber_alarmi", kw
    return None


def section_is_update_trap(section_text: str) -> Optional[str]:
    upper = section_text.upper()
    for kw in UPDATE_TRAP_KEYWORDS:
        if kw in upper:
            return kw
    return None


def send_pause_telegram(message: str) -> bool:
    """Haber şalteri — Mimar'a Telegram bildirimi."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[HALUK PDF] Telegram yok — {message}")
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        return True
    except Exception as e:
        print(f"[HALUK PDF] Telegram hatası: {e}")
        return False


# ── GÖREV 2: Section split & rule engine ───────────────────────────────────

def normalize_coin(raw: str) -> str:
    c = raw.upper().strip().replace("USDT", "")
    if c in MACRO_FILTER_COINS:
        return c
    return c + "USDT" if not c.endswith("USDT") else c


def leverage_for_coin(coin: str) -> int:
    base = coin.replace("USDT", "").upper()
    return 5 if base in LEVERAGE_5X_COINS else 2


def parse_price(val: str) -> Optional[float]:
    if not val:
        return None
    s = val.replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_entry_stop(section_text: str) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[float]]:
    entry_display = None
    entry_mid = None
    stop_display = None
    d1_price = None

    em = ENTRY_RE.search(section_text)
    if em:
        p1, p2 = em.group(1), (em.group(2) or "").strip()
        if p2:
            entry_display = f"{p1}-{p2}"
            a, b = parse_price(p1), parse_price(p2)
            if a is not None and b is not None:
                entry_mid = (a + b) / 2
        else:
            entry_display = p1
            entry_mid = parse_price(p1)

    sm = STOP_RE.search(section_text)
    if sm:
        stop_display = sm.group(1)
        d1_price = parse_price(sm.group(1))

    return entry_display, entry_mid, stop_display, d1_price


def infer_side(section_text: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit.upper()
    if SIDE_SHORT_RE.search(section_text) and not SIDE_LONG_RE.search(section_text):
        return "SHORT"
    if SIDE_LONG_RE.search(section_text):
        return "LONG"
    if re.search(r"short", section_text, re.I):
        return "SHORT"
    return "LONG"


def has_chart_structure(section_text: str, entry: Optional[str]) -> bool:
    """Grafik kutusu anahtar kelimesi veya giriş bölgesi/fiyatı varsa True."""
    if entry:
        return True
    return bool(CHART_KEYWORDS_RE.search(section_text))


def chart_approval_override(section_text: str, entry: Optional[str]) -> bool:
    """Pas/değil yazsa bile grafik + giriş bölgesi varsa ONAYLA (stop gerekmez)."""
    if not PAS_PHRASES.search(section_text):
        return True
    return has_chart_structure(section_text, entry)


def _extract_price_list(raw: str) -> List[float]:
    prices: List[float] = []
    for part in re.split(r"[,;/\s]+", raw):
        part = part.strip().replace("—", "-").replace("–", "-")
        if not part or part == "-":
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            for v in (a, b):
                p = parse_price(v)
                if p is not None:
                    prices.append(p)
            continue
        p = parse_price(part)
        if p is not None:
            prices.append(p)
    return sorted(set(prices))


def parse_macro_sr_levels(section_text: str) -> Tuple[List[float], List[float]]:
    """TOTAL/OTHERS bölümünden destek/direnç seviyelerini çıkar."""
    supports: List[float] = []
    resistances: List[float] = []
    for m in MACRO_SR_SUPPORT_RE.finditer(section_text):
        supports.extend(_extract_price_list(m.group(1)))
    for m in MACRO_SR_RESIST_RE.finditer(section_text):
        resistances.extend(_extract_price_list(m.group(1)))
    return sorted(set(supports)), sorted(set(resistances))


def infer_macro_direction(section_text: str) -> Optional[str]:
    upper = section_text.upper()
    if re.search(r"\b(YUKARI|YUKARIDA|BULL|LONG|ALIM)\b", upper):
        return "UP"
    if re.search(r"\b(AŞAĞI|ASAGI|BEAR|SHORT|SATIŞ|SATIS)\b", upper):
        return "DOWN"
    return None


def collect_panel_levels(sections: List[ParsedSection]) -> List[Dict[str, Any]]:
    """PDF bölümlerinden makro panel kayıtları."""
    from signal_bot.macro_levels_store import panel_key_for

    out: List[Dict[str, Any]] = []
    for sec in sections:
        key = panel_key_for(sec.coin)
        if not key:
            continue
        supports, resistances = parse_macro_sr_levels(sec.raw_text)
        snippet = re.sub(r"^[•\-\*]\s*", "", sec.raw_text.strip())[:400]
        out.append({
            "coin": key,
            "supports": supports,
            "resistances": resistances,
            "direction": infer_macro_direction(sec.raw_text),
            "text": snippet,
        })
    return out


def write_macro_levels(macro_filters: List[Dict[str, Any]], source: str) -> None:
    from signal_bot.macro_levels_store import merge_macro_levels

    merge_macro_levels(macro_filters, source)


def split_sections(full_text: str) -> List[ParsedSection]:
    sections: List[ParsedSection] = []
    markers: List[Tuple[int, str, Optional[str]]] = []

    for m in SECTION_HEADER_RE.finditer(full_text):
        coin = m.group(1).upper()
        if coin in NOT_COIN_TOKENS:
            continue
        markers.append((m.start(), coin, m.group(2)))

    known = set(KNOWN_COINS) | set(MACRO_FILTER_COINS)
    for m in BULLET_COIN_RE.finditer(full_text):
        coin = m.group(1).upper()
        if coin in NOT_COIN_TOKENS or coin not in known:
            continue
        if coin not in {x[1] for x in markers}:
            markers.append((m.start(), coin, None))

    if not markers:
        return [ParsedSection(coin="DOCUMENT", raw_text=full_text)]

    markers.sort(key=lambda x: x[0])
    for i, (start, coin, side) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)
        chunk = full_text[start:end].strip()
        if len(chunk) > 10:
            sections.append(ParsedSection(coin=coin, raw_text=chunk, side=side))

    return sections


def process_section(sec: ParsedSection, result: ParseResult) -> None:
    coin_base = sec.coin.replace("USDT", "").upper()

    if coin_base in MACRO_FILTER_COINS:
        supports, resistances = parse_macro_sr_levels(sec.raw_text)
        result.macro_filters.append({
            "coin": coin_base,
            "role": "F1_macro_direction",
            "text": sec.raw_text[:500],
            "supports": supports,
            "resistances": resistances,
            "direction": infer_macro_direction(sec.raw_text),
            "trade_allowed": False,
        })
        return

    trap = section_is_update_trap(sec.raw_text)
    if trap:
        result.rejected.append({
            "coin": normalize_coin(sec.coin),
            "reason": "update_trap",
            "keyword": trap,
            "action": "reject_new_position",
            "snippet": sec.raw_text[:200],
        })
        return

    entry_s, entry_mid, stop_s, d1_price = parse_entry_stop(sec.raw_text)
    side = infer_side(sec.raw_text, sec.side)

    if not chart_approval_override(sec.raw_text, entry_s):
        result.rejected.append({
            "coin": normalize_coin(sec.coin),
            "reason": "pas_without_chart",
            "action": "skip",
            "snippet": sec.raw_text[:200],
        })
        return

    has_entry_zone = bool(re.search(r"giriş\s*bolgesi|giris\s*bolgesi|entry\s*zone", sec.raw_text, re.I))
    has_chart = bool(CHART_KEYWORDS_RE.search(sec.raw_text)) or has_entry_zone
    has_entry = bool(entry_s or entry_mid is not None)
    if not (has_chart and has_entry):
        if re.search(r"|".join(KNOWN_COINS[:20]), sec.raw_text, re.I):
            result.rejected.append({
                "coin": normalize_coin(sec.coin),
                "reason": "no_chart_or_entry",
                "action": "skip",
                "snippet": sec.raw_text[:200],
            })
        return

    symbol = normalize_coin(sec.coin)
    lev = leverage_for_coin(symbol)
    approved = True

    signal = {
        "coin": symbol,
        "side": side,
        "leverage": lev,
        "leverage_label": f"{lev}x",
        "entry": entry_s or "—",
        "entry_price": entry_mid,
        "stop": stop_s or "—",
        "d1_price": d1_price,
        "d1_trigger_type": "spot_price",
        "tp1": None,
        "tp2": None,
        "status": "approved" if approved else "pending",
        "source": "HALUK_PDF",
        "chart_rule": "chart_defined_override" if PAS_PHRASES.search(sec.raw_text) else "standard",
    }
    result.signals.append(signal)


def parse_haluk_document(
    text: str,
    tables: Optional[List[List[List[str]]]] = None,
    source_label: str = "HALUK_PDF",
) -> ParseResult:
    """Ayrıştırılmış metin + tablolardan ParseResult üretir."""
    result = ParseResult(source=source_label)
    combined = text
    if tables:
        combined += "\n\n" + tables_to_text_snippets(tables)
        result.tables_count = len(tables)

    result.raw_text_length = len(combined)

    alarm = check_news_alarm(combined)
    if alarm:
        reason, kw = alarm
        result.system_pause = True
        result.pause_reason = reason
        result.pause_keyword = kw
        send_pause_telegram(
            "🛑 *MINA Haber Şalteri*\n\n"
            f"Tetikleyen: `{kw}`\n"
            "Sistem *PAUSE* — Manuel onay gerekli (Mimar)."
        )
        return result

    sections = split_sections(combined)
    for sec in sections:
        process_section(sec, result)

    panel = collect_panel_levels(sections)
    if panel:
        write_macro_levels(panel, source_label)
    elif result.macro_filters:
        write_macro_levels(result.macro_filters, source_label)

    return result


def parse_haluk_pdf(pdf_path: str) -> ParseResult:
    """PDF dosyasından tam parse pipeline."""
    text, tables = extract_pdf_content(pdf_path)
    source_label = f"HALUK_PDF:{os.path.basename(pdf_path)}"
    result = parse_haluk_document(text, tables, source_label=source_label)

    # Görsel makro SR — metin parser'a dokunmadan destek/direnç ekle
    if os.getenv("HALUK_VISUAL_MACRO", "1").strip().lower() not in ("0", "false", "no"):
        try:
            from signal_bot.haluk_pdf_visual import merge_visual_macro_levels

            visual_source = f"HALUK_PDF_VISUAL:{os.path.basename(pdf_path)}"
            levels = merge_visual_macro_levels(pdf_path, source=visual_source)
            if levels:
                print(
                    f"[HALUK PDF] Görsel makro SR: "
                    + ", ".join(f"{lv['coin']}" for lv in levels)
                )
        except Exception as exc:
            print(f"[HALUK PDF] Görsel makro analiz atlandı: {exc}")

    if os.getenv("HALUK_VISUAL_MACRO", "1").strip().lower() not in ("0", "false", "no"):
        try:
            from signal_bot.haluk_pdf_visual import extract_trading_signals

            pdf_signals = extract_trading_signals(pdf_path)
            if pdf_signals:
                print(
                    f"[HALUK PDF] Görsel trading sinyali: "
                    + ", ".join(f"{s['symbol']} {s['direction']}" for s in pdf_signals)
                )
        except Exception as exc:
            print(f"[HALUK PDF] Görsel trading sinyali atlandı: {exc}")

    return result


def parse_haluk_text_file(path: str) -> ParseResult:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return parse_haluk_document(text, source_label=f"HALUK_TEXT:{os.path.basename(path)}")


# ── GÖREV 4: RAW SIGNAL QUEUE ───────────────────────────────────────────────

def write_raw_signal_queue(result: ParseResult, merge: bool = False) -> str:
    """
    Katman 2 giyotin kuyruğuna JSON yazar.
    approval_bot hem raw_signal_queue hem ht_signals_queue okuyabilir.
    """
    payload = {
        "version": 1,
        "layer": "raw_signal_queue",
        "parsed_at": result.parsed_at,
        "source": result.source,
        "system_pause": result.system_pause,
        "pause_reason": result.pause_reason,
        "pause_keyword": result.pause_keyword,
        "macro_filters": result.macro_filters,
        "signals": result.signals,
        "rejected": result.rejected,
        "meta": {
            "raw_text_length": result.raw_text_length,
            "tables_count": result.tables_count,
            "signal_count": len(result.signals),
        },
    }

    if merge and os.path.exists(RAW_QUEUE_FILE):
        try:
            with open(RAW_QUEUE_FILE, encoding="utf-8") as f:
                old = json.load(f)
            payload["signals"] = old.get("signals", []) + payload["signals"]
            payload["rejected"] = old.get("rejected", []) + payload["rejected"]
        except Exception:
            pass

    os.makedirs(os.path.dirname(RAW_QUEUE_FILE), exist_ok=True)
    with open(RAW_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    also_ht = os.path.join(SIGNAL_BOT_DIR, "ht_signals_queue.json")
    if result.signals and not result.system_pause:
        ht_payload = {
            "signals": result.signals,
            "source": result.source,
            "macro_filters": result.macro_filters,
        }
        with open(also_ht, "w", encoding="utf-8") as f:
            json.dump(ht_payload, f, ensure_ascii=False, indent=2)

    return RAW_QUEUE_FILE


def process_pdf_to_queue(pdf_path: str) -> Dict[str, Any]:
    """Tek giriş: PDF → parse → kuyruk. Dict döner (test/CLI için)."""
    result = parse_haluk_pdf(pdf_path)
    path = write_raw_signal_queue(result)
    out = result.to_dict()
    out["queue_file"] = path
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python haluk_pdf_parser.py <dosya.pdf|.txt>")
        sys.exit(1)
    p = sys.argv[1]
    if p.endswith(".pdf"):
        r = process_pdf_to_queue(p)
    else:
        res = parse_haluk_text_file(p)
        write_raw_signal_queue(res)
        r = res.to_dict()
    print(json.dumps(r, ensure_ascii=False, indent=2))
