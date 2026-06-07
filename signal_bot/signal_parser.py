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
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_QUEUE_FILE = os.path.join(SIGNAL_BOT_DIR, "raw_signal_queue.json")
MERter_FILTER_LOG = os.path.join(SIGNAL_BOT_DIR, "merter_filter.log")

EMA_PERIOD = 20
ATR_PERIOD = 14
RSI_PERIOD = 14
RSI_OVERBOUGHT_LONG = 70.0  # Anayasa: RSI > 70 → LONG reddet
SR_ATR_MULT = 1.0
KLINES_15M_LIMIT = 80

_binance_client: Any = None

# ── Paylaşılan anayasa ───────────────────────────────────────────────────────
LEVERAGE_5X_BASES = frozenset({"BTC", "ETH", "XAU", "XAG"})
MACRO_FILTER_BASES = frozenset({
    "TOTAL", "OTHERS", "BRENT", "XCU", "DİĞER", "DIGER",
    "TOTAL2", "TOTAL3", "BTC.D", "USDT.D",
})
UPDATE_TRAP = frozenset({"UPDATE", "RETEST", "DURUM"})
NEWS_ALARM = ("FLASHCRASH", "MAYIN TARLASI", "BALINA SATIŞI", "BALINA SATISI")

COIN_ALIASES = {
    "SOLANA": "SOL",
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "RIPPLE": "XRP",
    "DOGECOIN": "DOGE",
    "GOOGLE": "GOOGLE",
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

# ── Merter kanal formatları (EI Bot / RSI Bot / sohbet) ─────────────────────
RE_EI_AL_SECTION = re.compile(
    r"🟢\s*\*\*Yeni AL Sinyalleri:\*\*\s*(.*?)(?=🔴\s*\*\*Yeni SAT|🕒|\Z)",
    re.IGNORECASE | re.DOTALL,
)
RE_EI_SAT_SECTION = re.compile(
    r"🔴\s*\*\*Yeni SAT Sinyalleri:\*\*\s*(.*?)(?=🟢\s*\*\*Yeni AL|🕒|\Z)",
    re.IGNORECASE | re.DOTALL,
)
RE_SYMBOL_LINK = re.compile(r"\[([A-Za-z0-9]+USDT)\]", re.IGNORECASE)
RE_PLAIN_USDT = re.compile(r"\b([A-Z0-9]{2,20}USDT)\b")
RE_RSI_ENTRY = re.compile(
    r"[🟢🔴]\s*\[\*\*([A-Za-z0-9]+USDT)\*\*\].*?(\(<20\)|\(>90\)).*?"
    r"RSI\(5dk\):\s*([\d.]+)(?:.*?Fiyat:\s*([\d.]+)\$)?",
    re.IGNORECASE | re.DOTALL,
)
RE_CHAT_BULL = re.compile(
    r"\b(al|alim|alım|long|yukari|yukarı|yukselis|yükseliş|devam|pozitif)\b",
    re.IGNORECASE,
)
RE_CHAT_BEAR = re.compile(
    r"\b(sat|satis|satış|short|asagi|aşağı|dusus|düşüş|stopla|negatif)\b",
    re.IGNORECASE,
)
RE_USDT_D = re.compile(r"usdt\.?\s*d\b", re.IGNORECASE)
RE_CHAT_SKIP = re.compile(
    r"docs\.google|Portf[oö]y Takibi|sess[iı]ze al|EI Trading Bot|RSI Analizi|Sinyal Taramas",
    re.IGNORECASE,
)
RE_DOLLAR_COIN = re.compile(r"\$([A-Za-z0-9]+)")

CHAT_COIN_BASES = frozenset(COIN_ALIASES.values()) | frozenset({
    "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "DOT", "LINK",
    "MATIC", "POL", "NEAR", "INJ", "SUI", "APT", "ARB", "OP", "LTC", "BCH",
    "GOOGLE",
})

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
RE_HALUK_SHORT_TICKER = re.compile(
    r"\b(" + "|".join(sorted(CHAT_COIN_BASES, key=len, reverse=True)) + r")\b",
    re.I,
)


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
    for pat, key in (
        (r"\bTOTAL3\b", "TOTAL3"),
        (r"\bTOTAL2\b", "TOTAL2"),
        (r"\bBTC\.?\s*D\b", "BTC.D"),
        (r"\bUSDT\.?\s*D\b", "USDT.D"),
        (r"\bOTHERS\b", "OTHERS"),
        (r"\bDIGER\b", "DIGER"),
        (r"\bTOTAL\b", "TOTAL"),
        (r"\bBRENT\b", "BRENT"),
        (r"\bXCU\b", "XCU"),
    ):
        if re.search(pat, upper):
            return key
    return None


def extract_haluk_symbol(text: str) -> str:
    """BCH, ETH, BTCUSDT, Google vb. → standart sembol."""
    if re.search(r"\bgoogle\b", text, re.I):
        return "GOOGLEUSDT"
    tm = RE_COIN_TICKER.search(text)
    if tm:
        return tm.group(1).upper() + "USDT"
    m = RE_HALUK_SHORT_TICKER.search(text)
    if m:
        base = m.group(1).upper()
        if base in COIN_ALIASES:
            base = COIN_ALIASES[base]
        return f"{base}USDT"
    macro = _macro_in_text(text)
    if macro:
        return "OTHERS" if macro in ("DIGER", "DİĞER") else macro
    return "UNKNOWN"


RE_GOOGLE_SHORT = re.compile(
    r"short[^.\n]{0,120}?([\d.,]+)\s*stop",
    re.I | re.S,
)
RE_GOOGLE_LONG = re.compile(
    r"long[^.\n]{0,120}?([\d.,]+)\s*destek",
    re.I | re.S,
)
RE_MAX_RISK_PCT = re.compile(
    r"(?:max\s*risk|kasa).*?([\d.,]+)\s*%",
    re.I,
)


def parse_haluk_google(text: str) -> List[Dict[str, Any]]:
    """Google çift pozisyon (Short stop + Long destek) mesajları."""
    if not re.search(r"\bgoogle\b", text, re.I):
        return []

    max_risk = None
    rm = RE_MAX_RISK_PCT.search(text)
    if rm:
        max_risk = _parse_num(rm.group(1))

    short_stop = None
    sm = RE_GOOGLE_SHORT.search(text)
    if sm:
        short_stop = _parse_num(sm.group(1))
    if short_stop is None:
        sm2 = re.search(r"short[^.\n]{0,80}?stop[^0-9]{0,10}([\d.,]+)", text, re.I | re.S)
        if sm2:
            short_stop = _parse_num(sm2.group(1))

    long_entry = None
    lm = RE_GOOGLE_LONG.search(text)
    if lm:
        long_entry = _parse_num(lm.group(1))
    if long_entry is None:
        lm2 = re.search(r"long[^.\n]{0,80}?destek[^0-9]{0,20}([\d.,]+)", text, re.I | re.S)
        if lm2:
            long_entry = _parse_num(lm2.group(1))

    records: List[Dict[str, Any]] = []
    extra = {"max_risk_pct": max_risk} if max_risk is not None else {}

    if short_stop is not None:
        rec = make_record(
            source="haluk_telegram",
            symbol="GOOGLEUSDT",
            direction="SHORT",
            entry_price=short_stop,
            stop_price=short_stop,
            status="approved",
            raw_text=text,
        )
        rec.update(extra)
        rec["note"] = "Google SHORT — stop seviyesi"
        records.append(rec)

    if long_entry is not None:
        rec = make_record(
            source="haluk_telegram",
            symbol="GOOGLEUSDT",
            direction="LONG",
            entry_price=long_entry,
            status="approved",
            raw_text=text,
        )
        rec.update(extra)
        rec["note"] = "Google LONG — destek bölgesi"
        records.append(rec)

    if records:
        return records

    if re.search(r"bekleyen|pozumuz|pozisyon", text, re.I):
        return [make_record(
            source="haluk_telegram",
            symbol="GOOGLEUSDT",
            direction=None,
            status="rejected",
            reject_reason="Google pozisyon — fiyat seviyesi parse edilemedi",
            raw_text=text,
        )]
    return []


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


# ── Merter bot filtreleri (EI / RSI) — Binance 15m teknik ───────────────────

def _get_binance_client() -> Any:
    global _binance_client
    if _binance_client is not None:
        return _binance_client
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in (root, os.path.join(root, "backend")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, ".env"))
        from config import BinanceConfig
        _binance_client = BinanceConfig().get_client()
    except Exception as e:
        print(f"[signal_parser] Binance client yok: {e}")
        _binance_client = None
    return _binance_client


def _log_filter_rejection(symbol: str, signal_format: str, reason: str, detail: Optional[Dict] = None) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] REJECT {signal_format} {symbol} — {reason}"
    if detail:
        line += f" | {json.dumps(detail, ensure_ascii=False)}"
    print(line, flush=True)
    try:
        with open(MERter_FILTER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _calc_ema(values: List[float], period: int = EMA_PERIOD) -> Optional[float]:
    if len(values) < period:
        return None
    ema = sum(values[:period]) / period
    mult = 2 / (period + 1)
    for v in values[period:]:
        ema = v * mult + ema * (1 - mult)
    return ema


def _calc_rsi(closes: List[float], period: int = RSI_PERIOD) -> Optional[float]:
    """Wilder RSI — son `period` kapanışı üzerinden."""
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_atr(klines: List[list], period: int = ATR_PERIOD) -> Optional[float]:
    if len(klines) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, len(klines)):
        h, l = float(klines[i][2]), float(klines[i][3])
        pc = float(klines[i - 1][4])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _swing_lows(klines: List[list], window: int = 2) -> List[float]:
    lows = [float(k[3]) for k in klines]
    out: List[float] = []
    for i in range(window, len(lows) - window):
        if all(lows[i] < lows[i - j] for j in range(1, window + 1)) and all(
            lows[i] < lows[i + j] for j in range(1, window + 1)
        ):
            out.append(lows[i])
    return out


def _swing_highs(klines: List[list], window: int = 2) -> List[float]:
    highs = [float(k[2]) for k in klines]
    out: List[float] = []
    for i in range(window, len(highs) - window):
        if all(highs[i] > highs[i - j] for j in range(1, window + 1)) and all(
            highs[i] > highs[i + j] for j in range(1, window + 1)
        ):
            out.append(highs[i])
    return out


def _ohlc(k: list) -> Tuple[float, float, float, float]:
    return float(k[1]), float(k[2]), float(k[3]), float(k[4])


def _is_sfp_candle(o: float, h: float, l: float, c: float, direction: str) -> bool:
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    if direction == "LONG":
        lower_wick = min(o, c) - l
        return lower_wick >= max(body * 1.5, rng * 0.33)
    upper_wick = h - max(o, c)
    return upper_wick >= max(body * 1.5, rng * 0.33)


def _is_pin_bar(o: float, h: float, l: float, c: float, direction: str) -> bool:
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    if direction == "LONG":
        lower_wick = min(o, c) - l
        return lower_wick / rng >= 0.55 and body / rng <= 0.30
    upper_wick = h - max(o, c)
    return upper_wick / rng >= 0.55 and body / rng <= 0.30


def _is_engulfing(prev: list, cur: list, direction: str) -> bool:
    po, _, _, pc = _ohlc(prev)
    co, _, _, cc = _ohlc(cur)
    if direction == "LONG":
        return pc < po and cc > co and co <= pc and cc >= po
    return pc > po and cc < co and co >= pc and cc <= po


def _candle_patterns(klines: List[list], direction: str) -> Tuple[bool, Optional[str]]:
    """Son kapalı 15m mum (+ bir önceki) üzerinde Pin / Engulfing / SFP."""
    if len(klines) < 3:
        return False, None
    prev, cur = klines[-3], klines[-2]
    o, h, l, c = _ohlc(cur)
    if _is_sfp_candle(o, h, l, c, direction):
        return True, "SFP"
    if _is_pin_bar(o, h, l, c, direction):
        return True, "pin_bar"
    if _is_engulfing(prev, cur, direction):
        return True, "engulfing"
    return False, None


class _MarketCache:
    def __init__(self) -> None:
        self.k15: Dict[str, List[list]] = {}
        self.mark: Dict[str, float] = {}

    def klines_15m(self, client: Any, symbol: str) -> List[list]:
        if symbol not in self.k15:
            for attempt in range(3):
                try:
                    self.k15[symbol] = client.futures_klines(
                        symbol=symbol, interval="15m", limit=KLINES_15M_LIMIT,
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        self.k15[symbol] = []
                    else:
                        time.sleep(0.4)
        return self.k15[symbol]

    def mark_price(self, client: Any, symbol: str) -> Optional[float]:
        if symbol not in self.mark:
            try:
                t = client.futures_mark_price(symbol=symbol)
                self.mark[symbol] = float(t["markPrice"])
            except Exception:
                self.mark[symbol] = None  # type: ignore[assignment]
        return self.mark.get(symbol)


def _near_sr_zone(klines: List[list], price: float, direction: str, atr: float) -> Tuple[bool, float]:
    """Fiyat taze destek/direnç bölgesinde mi (ATR toleransı içinde)."""
    if atr is None or atr <= 0:
        return False, 999.0
    lookback = klines[-48:] if len(klines) >= 48 else klines
    if direction == "LONG":
        supports = [s for s in _swing_lows(lookback) if s <= price]
        if not supports:
            return False, 999.0
        nearest = max(supports)
        dist = price - nearest
        return dist <= atr * SR_ATR_MULT, dist
    resistances = [r for r in _swing_highs(lookback) if r >= price]
    if not resistances:
        return False, 999.0
    nearest = min(resistances)
    dist = nearest - price
    return dist <= atr * SR_ATR_MULT, dist


def _filter_ei_candidate(
    client: Any,
    cache: _MarketCache,
    symbol: str,
    direction: str,
) -> Tuple[bool, str, float, Dict[str, Any]]:
    klines = cache.klines_15m(client, symbol)
    if len(klines) < EMA_PERIOD + 3:
        return False, "yetersiz 15m kline", 0.0, {}

    closes = [float(k[4]) for k in klines[:-1]]
    ema20 = _calc_ema(closes, EMA_PERIOD)
    mark = cache.mark_price(client, symbol)
    if ema20 is None or mark is None:
        return False, "EMA20 veya mark price alınamadı", 0.0, {}

    if direction == "LONG" and mark <= ema20:
        return False, "Adım1: fiyat EMA20 altında", 0.0, {"mark": mark, "ema20": ema20}
    if direction == "SHORT" and mark >= ema20:
        return False, "Adım1: fiyat EMA20 üstünde (SHORT)", 0.0, {"mark": mark, "ema20": ema20}

    if direction == "LONG":
        rsi = _calc_rsi(closes, RSI_PERIOD)
        if rsi is not None and rsi >= RSI_OVERBOUGHT_LONG:
            return False, f"Adım1b: RSI {rsi:.1f} >= 70 (aşırı alım, LONG reddedildi)", 0.0, {
                "mark": mark, "ema20": ema20, "rsi": round(rsi, 2),
            }

    atr = _calc_atr(klines[:-1], ATR_PERIOD)
    in_zone, sr_dist = _near_sr_zone(klines[:-1], mark, direction, atr or 0.0)
    if not in_zone:
        return False, "Adım2: destek/direnç bölgesinde değil (boşluk)", 0.0, {
            "mark": mark, "sr_dist": sr_dist, "atr": atr,
        }

    has_pattern, pattern = _candle_patterns(klines, direction)
    if not has_pattern:
        return False, "Adım3: Pin Bar / Engulfing / SFP yok", 0.0, {"mark": mark}

    ema_gap = abs(mark - ema20) / ema20 * 100 if ema20 else 0.0
    sr_score = max(0.0, 100.0 - (sr_dist / max(atr or 1e-9, 1e-9)) * 40.0)
    pattern_score = {"SFP": 40.0, "engulfing": 30.0, "pin_bar": 25.0}.get(pattern or "", 0.0)
    score = sr_score + pattern_score + max(0.0, 10.0 - ema_gap)
    meta = {
        "mark": mark,
        "ema20": round(ema20, 8),
        "atr": round(atr or 0, 8),
        "sr_dist": round(sr_dist, 8),
        "pattern": pattern,
        "filter_score": round(score, 2),
    }
    return True, "OK", score, meta


def _filter_rsi_candidate(
    client: Any,
    cache: _MarketCache,
    symbol: str,
    direction: str,
    rsi_5: Optional[float],
) -> Tuple[bool, str, float, Dict[str, Any]]:
    if rsi_5 is None:
        return False, "RSI(5dk) okunamadı", 0.0, {}

    if direction == "LONG" and rsi_5 >= 20:
        return False, f"RSI {rsi_5:.1f} >= 20 (aşırı satım şartı sağlanmadı)", 0.0, {"rsi_5m": rsi_5}
    if direction == "SHORT" and rsi_5 <= 80:
        return False, f"RSI {rsi_5:.1f} <= 80 (aşırı alım şartı sağlanmadı)", 0.0, {"rsi_5m": rsi_5}

    klines = cache.klines_15m(client, symbol)
    if len(klines) < 3:
        return False, "yetersiz 15m kline", 0.0, {}

    o, h, l, c = _ohlc(klines[-2])
    if not _is_sfp_candle(o, h, l, c, direction):
        return False, "son 15m mumda SFP iğnesi yok", 0.0, {"rsi_5m": rsi_5}

    mark = cache.mark_price(client, symbol)
    if mark is None:
        return False, "mark price alınamadı", 0.0, {}

    if direction == "LONG":
        score = max(0.0, 20.0 - rsi_5) * 5.0 + 30.0
    else:
        score = max(0.0, rsi_5 - 80.0) * 5.0 + 30.0

    meta = {
        "mark": mark,
        "rsi_5m": rsi_5,
        "pattern": "SFP",
        "filter_score": round(score, 2),
    }
    return True, "OK", score, meta


def _select_filtered_bot_record(
    candidates: List[Dict[str, Any]],
    signal_format: str,
) -> List[Dict[str, Any]]:
    """Bot adaylarından filtre geçen en yüksek skorlu tek kayıt."""
    if not candidates:
        return []

    client = _get_binance_client()
    if client is None:
        for c in candidates:
            _log_filter_rejection(
                c.get("symbol", "?"), signal_format, "Binance client kullanılamıyor",
            )
        return []

    cache = _MarketCache()
    best: Optional[Dict[str, Any]] = None
    best_score = -1.0

    for cand in candidates:
        symbol = cand["symbol"]
        direction = cand["direction"]
        fmt = cand.get("signal_format", signal_format)

        if fmt == "ei_scan":
            ok, reason, score, meta = _filter_ei_candidate(client, cache, symbol, direction)
        elif fmt == "rsi_bot":
            ok, reason, score, meta = _filter_rsi_candidate(
                client, cache, symbol, direction, cand.get("rsi_5m"),
            )
        else:
            continue

        if not ok:
            _log_filter_rejection(symbol, fmt, reason, meta or None)
            continue

        if score > best_score:
            best_score = score
            mark = meta.get("mark")
            best = _merter_record(
                symbol,
                direction,
                entry_price=mark,
                stop_price=None,
                signal_format=fmt,
                raw_text=cand.get("raw_snippet") or cand.get("raw_text"),
            )
            best["filter_score"] = meta.get("filter_score", score)
            best["filter_meta"] = meta
            if cand.get("rsi_5m") is not None:
                best["rsi_5m"] = cand["rsi_5m"]

    if best is None:
        return []
    return [best]


# ── KAYNAK 1: Merter ─────────────────────────────────────────────────────────

def _merter_record(
    symbol: str,
    direction: str,
    *,
    entry_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    reference_price: Optional[float] = None,
    signal_format: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    rec = make_record(
        source="merter",
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        tp_price=tp_price,
        status="approved",
        raw_text=raw_text,
    )
    if reference_price is not None:
        rec["reference_price"] = reference_price
    if signal_format:
        rec["signal_format"] = signal_format
    return rec


def _extract_usdt_symbols(segment: str) -> List[str]:
    found: List[str] = []
    seen = set()
    for m in RE_SYMBOL_LINK.finditer(segment):
        sym = normalize_symbol(m.group(1))
        if sym not in seen and sym not in MACRO_FILTER_BASES:
            seen.add(sym)
            found.append(sym)
    if not found:
        for m in RE_PLAIN_USDT.finditer(segment.upper()):
            sym = m.group(1)
            if sym not in seen and sym not in MACRO_FILTER_BASES:
                seen.add(sym)
                found.append(sym)
    return found


def _parse_ei_trading_bot(text: str) -> List[Dict[str, Any]]:
    """Format 1: EI Trading Bot — Yeni AL / SAT listeleri + 3 aşamalı filtre."""
    if "Yeni AL Sinyalleri" not in text and "Yeni SAT Sinyalleri" not in text:
        return []

    candidates: List[Dict[str, Any]] = []
    seen: set = set()
    for direction, pattern in (
        ("LONG", RE_EI_AL_SECTION),
        ("SHORT", RE_EI_SAT_SECTION),
    ):
        for m in pattern.finditer(text):
            for sym in _extract_usdt_symbols(m.group(1)):
                key = (sym, direction)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(_merter_record(
                    sym,
                    direction,
                    signal_format="ei_scan",
                    raw_text=text,
                ))
    return _select_filtered_bot_record(candidates, "ei_scan")


def _parse_rsi_bot(text: str) -> List[Dict[str, Any]]:
    """Format 2: RSI Bot — RSI<20 + 15m SFP filtre, tek coin."""
    if "RSI Analizi" not in text:
        return []

    candidates: List[Dict[str, Any]] = []
    for m in RE_RSI_ENTRY.finditer(text):
        symbol = normalize_symbol(m.group(1))
        zone = m.group(2)
        rsi_5 = _parse_num(m.group(3))
        if "(<20)" in zone:
            direction = "LONG"
        elif "(>90)" in zone:
            direction = "SHORT"
        else:
            continue
        rec = _merter_record(
            symbol,
            direction,
            signal_format="rsi_bot",
            raw_text=text,
        )
        if rsi_5 is not None:
            rec["rsi_5m"] = rsi_5
        candidates.append(rec)
    return _select_filtered_bot_record(candidates, "rsi_bot")


def _parse_merter_legacy_structured(text: str) -> List[Dict[str, Any]]:
    """Eski yapılandırılmış Merter: solana var / $COIN için Long."""
    records: List[Dict[str, Any]] = []

    chat = RE_SOLANA_CHAT.search(text)
    if chat:
        coin_raw, maliyet = chat.group(1), _parse_num(chat.group(2))
        symbol = normalize_symbol(coin_raw)
        entry: Optional[float] = maliyet
        tp = None
        satim = RE_CIFT_SATIM.search(text)
        if satim:
            tp = _mid(_parse_num(satim.group(1)), _parse_num(satim.group(2)))
        alim = RE_CIFT_ALIM.search(text)
        if alim and entry is None:
            entry = _mid(_parse_num(alim.group(1)), _parse_num(alim.group(2)))
        records.append(_merter_record(
            symbol,
            "LONG",
            entry_price=entry,
            tp_price=tp,
            signal_format="legacy_chat",
            raw_text=text,
        ))
        return records

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
        mal = RE_MALIYET.search(text)
        if mal:
            entry = _parse_num(mal.group(1))
        alim = RE_CIFT_ALIM.search(text)
        satim = RE_CIFT_SATIM.search(text)
        if alim:
            entry = entry or _mid(_parse_num(alim.group(1)), _parse_num(alim.group(2)))
        if satim:
            tp = _mid(_parse_num(satim.group(1)), _parse_num(satim.group(2)))

    records.append(_merter_record(
        symbol,
        direction,
        entry_price=entry,
        stop_price=stop,
        tp_price=tp,
        signal_format="legacy_dollar",
        raw_text=text,
    ))
    return records


def _chat_macro_direction(text: str) -> Optional[str]:
    upper = _norm_upper(text)
    if RE_USDT_D.search(text):
        if re.search(r"DESTEK\s+UST|DESTEK USTU|DESTEK UST", upper):
            return "LONG"
        if re.search(r"DESTEK\s+ALT|DESTEK ALTI", upper):
            return "SHORT"
    bull = len(RE_CHAT_BULL.findall(text))
    bear = len(RE_CHAT_BEAR.findall(text))
    if bull > bear:
        return "LONG"
    if bear > bull:
        return "SHORT"
    return None


def _extract_chat_coins(text: str) -> List[str]:
    found: List[str] = []
    seen = set()
    for m in RE_COIN_TICKER.finditer(text):
        sym = normalize_symbol(m.group(1))
        if sym not in seen:
            seen.add(sym)
            found.append(sym)
    for m in RE_DOLLAR_COIN.finditer(text):
        sym = normalize_symbol(m.group(1))
        if sym not in seen and sym not in MACRO_FILTER_BASES:
            seen.add(sym)
            found.append(sym)
    upper = _norm_upper(text)
    for m in re.finditer(r"\b([A-Z0-9]{2,12})\b", upper):
        base = m.group(1)
        if base in CHAT_COIN_BASES:
            sym = normalize_symbol(base)
            if sym not in seen:
                seen.add(sym)
                found.append(sym)
    for alias, sym in COIN_ALIASES.items():
        if re.search(rf"\b{_norm_upper(alias)}\b", upper):
            norm = normalize_symbol(sym)
            if norm not in seen:
                seen.add(norm)
                found.append(norm)
    return found


def _parse_merter_chat(text: str) -> List[Dict[str, Any]]:
    """Format 3: Merter sohbet — coin + yön çıkarımı (giriş/stop yok)."""
    if RE_CHAT_SKIP.search(text):
        return []
    if text.startswith("📊"):
        return []

    direction = _chat_macro_direction(text)
    coins = _extract_chat_coins(text)
    if not direction or not coins:
        return []

    mal = RE_MALIYET.search(text)
    entry = _parse_num(mal.group(1)) if mal else None
    gs = RE_GIRIS_STOP.search(text)
    if gs:
        entry = _parse_num(gs.group(1))
        stop = _parse_num(gs.group(2))
    else:
        stop = None

    records: List[Dict[str, Any]] = []
    for sym in coins:
        records.append(_merter_record(
            sym,
            direction,
            entry_price=entry,
            stop_price=stop,
            signal_format="merter_chat",
            raw_text=text,
        ))
    return records


def parse_merter(text: str) -> List[Dict[str, Any]]:
    """Merter Telegram — legacy + sohbet (EI/RSI → merter_dca_manager)."""
    text = text.strip()
    if not text:
        return []

    for parser in (
        _parse_merter_legacy_structured,
        _parse_merter_chat,
    ):
        records = parser(text)
        if records:
            return records
    return []


def _upsert_telegram_macro(text: str, source: str = "haluk_telegram") -> None:
    """Telegram makro/özet mesajını macro_levels.json'a yaz."""
    try:
        from signal_bot.haluk_pdf_parser import infer_macro_direction, parse_macro_sr_levels
        from signal_bot.macro_levels_store import detect_panel_coins_in_text, merge_macro_levels, panel_key_for
    except ImportError:
        return

    coins = detect_panel_coins_in_text(text)
    if not coins:
        key = panel_key_for(extract_haluk_symbol(text))
        if key:
            coins = [key]

    if not coins:
        return

    supports, resistances = parse_macro_sr_levels(text)
    snippet = text.strip()[:400]
    direction = infer_macro_direction(text)
    rows = [
        {
            "coin": c,
            "supports": supports,
            "resistances": resistances,
            "direction": direction,
            "text": snippet,
        }
        for c in coins
    ]
    merge_macro_levels(rows, source)


# ── KAYNAK 2: Haluk Telegram ─────────────────────────────────────────────────

def parse_haluk_telegram(text: str) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Haluk Hoca Telegram mesajı.
    Returns: (records, system_pause)
    """
    text = text.strip()
    if not text:
        return [], False

    google_recs = parse_haluk_google(text)
    if google_recs:
        return google_recs, False

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
        _upsert_telegram_macro(text)
        return [make_record(
            source="haluk_telegram",
            symbol=sym,
            direction=None,
            status="macro",
            reject_reason=None,
            raw_text=text,
        )], False

    trap = _update_trap(text)
    symbol = extract_haluk_symbol(text)

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

    has_chart = bool(re.search(r"grafik|kutu|giriş\s*kutusu|giris\s*kutusu|entry\s*box|chart", text, re.I))
    pas = bool(PAS_RE.search(text))

    if pas and not (has_chart and entry):
        return [make_record(
            source="haluk_telegram",
            symbol=symbol,
            direction=None,
            status="rejected",
            reject_reason="Pas — grafik ve giriş bölgesi eksik",
            raw_text=text,
        )], False

    direction = "LONG"
    sm = RE_HALUK_SIDE.search(text)
    if sm and sm.group(1).lower() in ("short", "satış", "satis"):
        direction = "SHORT"

    if not (has_chart and entry):
        pos_mgmt = re.search(
            r"karda|kar\s*al|stop\s*at|tp['']?yi|pozisyon|pozumuz|bekleyen",
            text,
            re.I,
        )
        if pos_mgmt and symbol != "UNKNOWN":
            return [make_record(
                source="haluk_telegram",
                symbol=symbol,
                direction=None,
                status="rejected",
                reject_reason="pozisyon yönetimi — yeni giriş yok",
                raw_text=text,
            )], False
        return [], False

    return [make_record(
        source="haluk_telegram",
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        status="approved",
        reject_reason=None,
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
        coin = m["coin"] if str(m["coin"]).endswith("USDT") else f"{m['coin']}USDT"
        rec = make_record(
            source="haluk_pdf",
            symbol=coin,
            direction=None,
            status="macro",
            reject_reason=None,
            raw_text=m.get("text", "")[:200],
        )
        rec["macro_role"] = "F1"
        rec["supports"] = m.get("supports") or []
        rec["resistances"] = m.get("resistances") or []
        rec["macro_direction"] = m.get("direction")
        records.append(rec)

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


HALUK_PDF_SOURCES = frozenset({"haluk_pdf"})


def pdf_timestamp_from_path(pdf_path: str) -> str:
    """PDF dosya adından veya mtime'dan sıralanabilir UTC timestamp."""
    base = os.path.basename(pdf_path)
    m = re.match(r"tg_(\d{8})_(\d{6})", base)
    if m:
        d, t = m.group(1), m.group(2)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}Z"
    try:
        mtime = os.path.getmtime(pdf_path)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return _now_iso()


def _cancel_superseded_haluk_limits(superseded: List[Dict[str, Any]]) -> None:
    """Eski PDF'den bekleyen limit emirlerini iptal et."""
    to_cancel: List[Tuple[str, int]] = []
    for entry in superseded:
        if entry.get("queue_state") != "pending_limit":
            continue
        sym = entry.get("symbol")
        oid = entry.get("pending_order_id")
        if sym and oid:
            to_cancel.append((sym, int(oid)))

    if not to_cancel:
        return

    try:
        client = _get_binance_client()
    except Exception:
        client = None
    if client is None:
        print(f"[HALUK PDF] {len(to_cancel)} eski limit emri iptal edilemedi (client yok)")
        return

    import mina_tracking as mt

    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    for sym, oid in to_cancel:
        try:
            client.futures_cancel_order(symbol=sym, orderId=oid)
            print(f"[HALUK PDF] Eski limit iptal: {sym} order={oid}")
        except Exception as e:
            print(f"[HALUK PDF] Limit iptal hatası {sym} {oid}: {e}")
        for pk, info in list(pending.items()):
            if info.get("order_id") == oid and info.get("symbol") == sym:
                pending.pop(pk, None)
    mt.save_json(mt.PENDING_ORDERS_FILE, pending)


def supersede_stale_haluk_pdf_entries(
    data: Dict[str, Any],
    new_pdf_ts: str,
    pdf_path: str,
) -> List[Dict[str, Any]]:
    """
    Yeni PDF geldiğinde önceki haluk_pdf kayıtlarını geçersiz say.
    consumed (işleme dönmüş) kayıtlara dokunulmaz.
    """
    superseded: List[Dict[str, Any]] = []
    old_ts = data.get("haluk_pdf_timestamp")

    for entry in data.get("entries") or []:
        if entry.get("source") not in HALUK_PDF_SOURCES:
            continue
        if entry.get("queue_state") == "consumed":
            continue
        if entry.get("status") == "superseded":
            continue

        entry["status"] = "superseded"
        entry["queue_state"] = "cancelled"
        entry["superseded_at"] = _now_iso()
        entry["superseded_by_pdf"] = new_pdf_ts
        entry["superseded_reason"] = "yeni_pdf"
        if old_ts:
            entry["replaced_pdf_timestamp"] = old_ts
        superseded.append(entry)

    if superseded:
        print(
            f"[HALUK PDF] {len(superseded)} eski PDF kaydı geçersiz "
            f"(yeni={new_pdf_ts}, eski={old_ts or '—'})"
        )
        _cancel_superseded_haluk_limits(superseded)

    data["haluk_pdf_timestamp"] = new_pdf_ts
    data["haluk_pdf_path"] = pdf_path
    data["haluk_pdf_received_at"] = _now_iso()
    return superseded


def enqueue_haluk_pdf_records(pdf_path: str, records: List[Dict[str, Any]]) -> str:
    """Haluk PDF kayıtları — en güncel PDF kuralı (eski PDF sinyalleri iptal)."""
    if not records:
        return RAW_QUEUE_FILE

    pdf_ts = pdf_timestamp_from_path(pdf_path)
    data = load_queue()
    if "entries" not in data:
        data["entries"] = []

    supersede_stale_haluk_pdf_entries(data, pdf_ts, pdf_path)

    for rec in records:
        if rec.get("source") in HALUK_PDF_SOURCES or rec.get("source") == "haluk_pdf":
            rec["pdf_timestamp"] = pdf_ts
            rec["pdf_path"] = os.path.basename(pdf_path)

    data["entries"].extend(records)
    path = save_queue(data)

    approved = [
        r for r in records
        if r.get("status") == "approved" and r.get("symbol") != "SYSTEM"
    ]
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
                    "pdf_timestamp": pdf_ts,
                }
                for r in approved
            ],
            "source": f"haluk_pdf:{os.path.basename(pdf_path)}",
            "pdf_timestamp": pdf_ts,
        }
        ht_path = os.path.join(SIGNAL_BOT_DIR, "ht_signals_queue.json")
        with open(ht_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False, indent=2)

    return path


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
        enqueue_haluk_pdf_records(pdf_path, records)
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
