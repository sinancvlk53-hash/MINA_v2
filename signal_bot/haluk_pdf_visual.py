# -*- coding: utf-8 -*-
"""
Haluk PDF — görsel makro seviye analizi (Claude Vision).

Sarı kutucuklar ve yatay çizgilerden destek/direnç çıkarır.
Mevcut metin parser'a dokunmaz; yalnızca macro_levels.json SR alanlarını günceller.
"""

from __future__ import annotations

import base64
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from signal_bot.macro_levels_store import MACRO_PANEL_COINS, panel_key_for, merge_macro_levels

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
HT_SIGNALS_QUEUE_FILE = os.path.join(SIGNAL_BOT_DIR, "ht_signals_queue.json")
_page_analysis_cache: Dict[str, List[Dict[str, Any]]] = {}

VISUAL_MACRO_SYMBOLS = (
    "TOTAL", "OTHERS", "BTC.D", "USDT.D", "BTC", "ETH", "XAU", "XAG", "BRENT", "TOTAL2", "TOTAL3",
)

CLAUDE_MODEL = os.getenv("HALUK_VISUAL_MODEL", "claude-sonnet-4-6")
MAX_PAGES = int(os.getenv("HALUK_VISUAL_MAX_PAGES", "10"))
RENDER_DPI = int(os.getenv("HALUK_VISUAL_DPI", "144"))

VISION_PROMPT = """Bu görüntü Haluk Hoca'nın kripto/makro analiz PDF'inin bir sayfasıdır.

GÖREV: Sayfadaki grafikleri incele. Özellikle:
- Sarı/turuncu kutucuklar içindeki fiyat seviyeleri
- Yatay destek/direnç çizgileri (genelde etiketli fiyatlar)
- Grafik başlığı veya üst/yan etiketlerdeki sembol adı

Sadece şu makro semboller için seviye çıkar (sayfada yoksa atla):
TOTAL, OTHERS, BTC.D, USDT.D, BTC, ETH, XAU, XAG, BRENT, TOTAL2, TOTAL3

Kurallar:
- supports: destek / alt yatay seviyeler (büyükten küçüğe sırala)
- resistances: direnç / üst yatay seviyeler (büyükten küçüğe sırala)
- Fiyatları sayı olarak ver (virgül değil nokta). TOTAL/TOTAL2/TOTAL3 için indeks değerleri olabilir.
- BTC → sembol "BTC" (USD fiyat), ETH → sembol "ETH", XAU/XAG aynı kalır
- Tahmin etme; net görünmeyen seviyeyi yazma
- Sadece geçerli JSON döndür, markdown yok

Format:
{{"charts":[{{"symbol":"TOTAL","supports":[1.91,1.85],"resistances":[2.05,2.10]}}]}}

Sayfa {page_num}. Grafik yoksa: {{"charts":[]}}"""

TRADING_SIGNAL_PROMPT = """Bu görüntü Haluk Hoca'nın kripto analiz PDF'inin bir sayfasıdır.

GÖREV: Sayfada TradingView pozisyon aracı ara.

POZİSYON ARACI — yeşil ve kırmızı iki renkli dikdörtgen varsa sinyal say.
Büyük küçük fark etmez, soluk da olsa say. Sohbet/yorumları yok say, sadece grafiğe bak.

BU ARAÇ YOKSA → {{"signals": []}}

YÖN TESPİTİ — TEMEL KURAL:
TradingView Position Tool'da YEŞİL rengin yönüne bak:

- Yeşil YUKARI doğru büyükse (yeşil üstte) → LONG
- Yeşil AŞAĞI doğru büyükse (yeşil altta) → SHORT

Kırmızı her zaman yeşilin tersindedir, ona bakma.
Sadece yeşilin nereye baktığına bak.

Giriş (entry) = yeşil ve kırmızının birleştiği çizgi
TP = yeşilin dış ucu (yeşilin baktığı yön)
Stop = kırmızının dış ucu (yeşilin tersi)

İKİ YÖNLÜ POZİSYON:
Aynı grafikte iki ayrı Position Tool varsa ikisini de yaz.
Üstteki ve alttaki ayrı ayrı değerlendir.
Her biri için ayrı sinyal üret.

ZEC ÖRNEĞI:
Üstte: yeşil aşağı büyük → SHORT, giriş 541.42, TP 325.28, stop 629.15
Altta: yeşil yukarı büyük → LONG, giriş 378.38, TP 629.15, stop 325.28

ARAÇ VARSA:
- symbol: grafik başlığındaki coin (BTCUSDT → BTC, ETHUSDT → ETH)
- direction: "LONG" veya "SHORT" (yukarıdaki tek kurala göre)
- entry, tp, stop: yukarıdaki entry/tp/stop kurallarına göre sayısal fiyat

Sadece geçerli JSON döndür:
{{"signals": [{{"symbol": "BTC", "direction": "LONG",
"entry": 61576.0, "tp": 64360.0, "stop": 60184.0}}]}}

Sayfa {page_num}."""

VERIFY_PROMPT = """
Bir önceki analizde şu sinyaller bulundu: {signals}

Şimdi sadece YÖN doğrulaması yap:
Her sinyal için grafiğe tekrar bak.
- LONG için: yeşil alan kırmızıdan BÜYÜK olmalı
- SHORT için: kırmızı alan yeşilden BÜYÜK olmalı

Eğer yön yanlışsa düzelt.
Eğer emin değilsen o sinyali listeden çıkar.
Sadece JSON döndür: {{"verified_signals": [...]}}
"""


def _anthropic_client():
    import anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY tanımlı değil")
    return anthropic.Anthropic(api_key=key)


def render_pdf_pages_png(pdf_path: str, dpi: int = RENDER_DPI) -> List[Tuple[int, bytes]]:
    """PDF sayfalarını PNG byte listesine çevirir."""
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ImportError("pymupdf gerekli: pip install pymupdf") from e

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)

    doc = fitz.open(pdf_path)
    pages: List[Tuple[int, bytes]] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for idx in range(min(len(doc), MAX_PAGES)):
            page = doc[idx]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append((idx + 1, pix.tobytes("png")))
    finally:
        doc.close()
    return pages


def _parse_claude_json(text: str, *, empty: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fallback = empty if empty is not None else {"charts": []}
    text = (text or "").strip()
    if not text:
        return dict(fallback)
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            key = "signals" if "signals" in fallback else "charts"
            return {key: data}
        return data if isinstance(data, dict) else dict(fallback)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    print(f"[HALUK VISUAL] JSON parse edilemedi: {text[:200]}...")
    return dict(fallback)


def _vision_call(client, png_bytes: bytes, prompt: str) -> str:
    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)


def _normalize_levels(values: Any) -> List[float]:
    out: List[float] = []
    if not isinstance(values, list):
        return out
    for v in values:
        try:
            out.append(round(float(v), 6))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def _signal_match_key(sig: Dict[str, Any]) -> tuple:
    sym = _normalize_ht_symbol(str(sig.get("symbol") or sig.get("coin") or ""))
    direction = str(sig.get("direction") or sig.get("side") or "").upper()
    return sym, direction


def _verify_trading_signals(
    client,
    png_bytes: bytes,
    initial_signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """İkinci Claude çağrısı — yön doğrulama; çelişen coin atlanır."""
    if not initial_signals:
        return []

    signals_json = json.dumps(initial_signals, ensure_ascii=False)
    prompt = VERIFY_PROMPT.format(signals=signals_json)
    verify_text = _vision_call(client, png_bytes, prompt)
    verified = _parse_claude_json(verify_text, empty={"verified_signals": []})
    verified_list = verified.get("verified_signals") or []

    verified_keys: set = set()
    for v in verified_list:
        if not isinstance(v, dict):
            continue
        key = _signal_match_key(v)
        if key[0] and key[1] in ("LONG", "SHORT"):
            verified_keys.add(key)

    confirmed: List[Dict[str, Any]] = []
    for sig in initial_signals:
        if not isinstance(sig, dict):
            continue
        key = _signal_match_key(sig)
        sym, direction = key
        if not sym or direction not in ("LONG", "SHORT"):
            continue
        if key in verified_keys:
            confirmed.append(sig)
        else:
            print(
                f"[HALUK VISUAL] doğrulama atladı: {sym} {direction} "
                f"(verify={list(verified_keys)})"
            )
    return confirmed


def analyze_page_image(client, png_bytes: bytes, page_num: int) -> Dict[str, Any]:
    """Tek sayfa PNG → makro charts + çift doğrulamalı trading signals."""
    macro_text = _vision_call(client, png_bytes, VISION_PROMPT.format(page_num=page_num))
    signal_text = _vision_call(client, png_bytes, TRADING_SIGNAL_PROMPT.format(page_num=page_num))
    macro = _parse_claude_json(macro_text, empty={"charts": []})
    trading = _parse_claude_json(signal_text, empty={"signals": []})
    raw_signals = trading.get("signals") or []
    verified_signals = _verify_trading_signals(client, png_bytes, raw_signals)
    return {
        "charts": macro.get("charts") or [],
        "signals": verified_signals,
    }


def aggregate_chart_levels(page_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sayfa sonuçlarını coin bazında birleştir."""
    by_coin: Dict[str, Dict[str, set]] = defaultdict(lambda: {"supports": set(), "resistances": set()})

    for page in page_results:
        for chart in page.get("charts") or []:
            if not isinstance(chart, dict):
                continue
            sym = str(chart.get("symbol") or chart.get("coin") or "").strip()
            key = panel_key_for(sym)
            if not key:
                continue
            sup = _normalize_levels(chart.get("supports"))
            res = _normalize_levels(chart.get("resistances"))
            by_coin[key]["supports"].update(sup)
            by_coin[key]["resistances"].update(res)

    out: List[Dict[str, Any]] = []
    for coin in MACRO_PANEL_COINS:
        if coin not in by_coin:
            continue
        supports = sorted(by_coin[coin]["supports"], reverse=True)
        resistances = sorted(by_coin[coin]["resistances"], reverse=True)
        if not supports and not resistances:
            continue
        out.append({
            "coin": coin,
            "supports": supports,
            "resistances": resistances,
        })
    return out


def _pdf_cache_key(pdf_path: str) -> str:
    try:
        st = os.stat(pdf_path)
        return f"{pdf_path}:{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return pdf_path


def _analyze_pdf_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """PDF sayfalarını vision ile analiz et (aynı dosya için tek tarama)."""
    cache_key = _pdf_cache_key(pdf_path)
    cached = _page_analysis_cache.get(cache_key)
    if cached is not None:
        return cached

    pages = render_pdf_pages_png(pdf_path)
    if not pages:
        return []

    client = _anthropic_client()
    page_results: List[Dict[str, Any]] = []
    for page_num, png in pages:
        try:
            page_results.append(analyze_page_image(client, png, page_num))
        except Exception as exc:
            print(f"[HALUK VISUAL] sayfa {page_num} hata: {exc}")
            page_results.append({"charts": [], "signals": []})

    if len(_page_analysis_cache) > 8:
        _page_analysis_cache.clear()
    _page_analysis_cache[cache_key] = page_results
    return page_results


def extract_visual_macro_levels(pdf_path: str) -> List[Dict[str, Any]]:
    """PDF tüm sayfalar → görsel makro destek/direnç listesi."""
    page_results = _analyze_pdf_pages(pdf_path)
    if not page_results:
        print(f"[HALUK VISUAL] Sayfa yok: {pdf_path}")
        return []

    for idx, result in enumerate(page_results, start=1):
        charts = result.get("charts") or []
        if charts:
            print(
                f"[HALUK VISUAL] sayfa {idx}: "
                + ", ".join(
                    f"{c.get('symbol', '?')} S={len(c.get('supports') or [])} R={len(c.get('resistances') or [])}"
                    for c in charts
                    if isinstance(c, dict)
                )
            )

    levels = aggregate_chart_levels(page_results)
    print(f"[HALUK VISUAL] {len(levels)} makro sembol SR güncellenecek")
    return levels


def merge_visual_macro_levels(pdf_path: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Görsel analiz yap ve macro_levels.json'a yalnızca supports/resistances yaz.
    Snippet ve direction mevcut metin parser kaydından korunur.
    """
    levels = extract_visual_macro_levels(pdf_path)
    if not levels:
        return []
    src = source or f"HALUK_PDF_VISUAL:{os.path.basename(pdf_path)}"
    merge_macro_levels(levels, src)
    return levels


def extract_and_merge_visual_macro_levels(pdf_path: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
    """haluk_pdf_parser entegrasyon noktası."""
    return merge_visual_macro_levels(pdf_path, source)


def _normalize_ht_symbol(raw: str) -> str:
    sym = str(raw or "").upper().strip()
    if not sym:
        return ""
    if sym.endswith("USDT"):
        return sym
    return sym + "USDT"


def _parse_signal_price(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return round(float(str(val).replace(",", ".")), 8)
    except (TypeError, ValueError):
        return None


def _raw_signal_to_queue_record(sig: Dict[str, Any], pdf_path: str) -> Optional[Dict[str, Any]]:
    symbol = _normalize_ht_symbol(sig.get("symbol"))
    direction = str(sig.get("direction") or "").upper()
    entry = _parse_signal_price(sig.get("entry"))
    tp = _parse_signal_price(sig.get("tp"))
    stop = _parse_signal_price(sig.get("stop"))
    if not symbol or direction not in ("LONG", "SHORT"):
        return None
    if entry is None or tp is None or stop is None:
        return None
    pdf_name = os.path.basename(pdf_path)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry,
        "tp_price": tp,
        "stop_price": stop,
        "source": "haluk_pdf",
        "status": "approved",
        "timestamp": ts,
        "pdf_file": pdf_name,
    }


def _write_ht_signals_queue(records: List[Dict[str, Any]], pdf_path: str) -> None:
    from mina_ht_pdf_supersede import (
        get_binance_client_optional,
        normalize_ht_symbol,
        supersede_ht_pdf_coins,
        signal_symbol,
    )

    new_symbols = [
        normalize_ht_symbol(r.get("symbol"))
        for r in records
        if r.get("symbol")
    ]
    client = get_binance_client_optional()
    if new_symbols:
        supersede_ht_pdf_coins(new_symbols, client)

    kept: List[Dict[str, Any]] = []
    new_symbol_set = set(new_symbols)
    if os.path.isfile(HT_SIGNALS_QUEUE_FILE):
        try:
            with open(HT_SIGNALS_QUEUE_FILE, encoding="utf-8") as f:
                old = json.load(f)
            kept = [
                s for s in (old.get("signals") or [])
                if signal_symbol(s) not in new_symbol_set
            ]
        except (OSError, json.JSONDecodeError):
            pass

    payload: Dict[str, Any] = {
        "signals": kept + records,
        "source": f"HALUK_PDF_VISUAL:{os.path.basename(pdf_path)}",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    os.makedirs(SIGNAL_BOT_DIR, exist_ok=True)
    with open(HT_SIGNALS_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[HALUK VISUAL] {len(records)} sinyal → {HT_SIGNALS_QUEUE_FILE}")
    for rec in records:
        try:
            from mina_motor_telegram import notify_ht_signal_queued
            notify_ht_signal_queued(rec, source_info=payload.get("source", ""))
        except Exception as exc:
            print(f"[HALUK VISUAL] Telegram bildirimi atlandı: {exc}")


def _log_ht_pdf_signals_journal(records: List[Dict[str, Any]]) -> None:
    try:
        from mina_trading_journal import TradingJournal

        root = os.environ.get(
            "MINA_DATA_ROOT",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        journal = TradingJournal(db_path=os.path.join(root, "mina_trading_journal.db"))
        for rec in records:
            journal.log_ht_pdf_signal(rec)
        journal.close()
    except Exception as exc:
        print(f"[HALUK VISUAL] ht_pdf_basari_orani journal hatası: {exc}")


def extract_trading_signals(pdf_path: str) -> List[Dict[str, Any]]:
    """PDF sayfalarından TradingView Long/Short Position sinyallerini çıkar."""
    page_results = _analyze_pdf_pages(pdf_path)
    if not page_results:
        print(f"[HALUK VISUAL] Trading sinyali — sayfa yok: {pdf_path}")
        return []

    records: List[Dict[str, Any]] = []
    for page_num, result in enumerate(page_results, start=1):
        for sig in result.get("signals") or []:
            if not isinstance(sig, dict):
                continue
            rec = _raw_signal_to_queue_record(sig, pdf_path)
            if rec:
                records.append(rec)
                print(
                    f"[HALUK VISUAL] sinyal sayfa {page_num}: "
                    f"{rec['symbol']} {rec['direction']} entry={rec['entry_price']}"
                )

    if not records:
        print(f"[HALUK VISUAL] Trading sinyali bulunamadı: {pdf_path}")
        return []

    _write_ht_signals_queue(records, pdf_path)
    _log_ht_pdf_signals_journal(records)
    print(f"[HALUK VISUAL] Toplam {len(records)} trading sinyali kaydedildi")
    return records
