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
from typing import Any, Dict, List, Optional, Tuple

from signal_bot.macro_levels_store import MACRO_PANEL_COINS, panel_key_for, merge_macro_levels

VISUAL_MACRO_SYMBOLS = (
    "TOTAL", "OTHERS", "BTC.D", "USDT.D", "BTC", "ETH", "XAU", "XAG", "BRENT", "TOTAL2", "TOTAL3",
)

CLAUDE_MODEL = os.getenv("HALUK_VISUAL_MODEL", "claude-sonnet-4-6")
MAX_PAGES = int(os.getenv("HALUK_VISUAL_MAX_PAGES", "24"))
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


def _parse_claude_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"charts": []}
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {"charts": data}
        return data if isinstance(data, dict) else {"charts": []}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    print(f"[HALUK VISUAL] JSON parse edilemedi: {text[:200]}...")
    return {"charts": []}


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


def analyze_page_image(client, png_bytes: bytes, page_num: int) -> Dict[str, Any]:
    """Tek sayfa PNG → Claude vision → charts dict."""
    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    prompt = VISION_PROMPT.format(page_num=page_num)
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
    return _parse_claude_json("\n".join(parts))


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


def extract_visual_macro_levels(pdf_path: str) -> List[Dict[str, Any]]:
    """PDF tüm sayfalar → görsel makro destek/direnç listesi."""
    pages = render_pdf_pages_png(pdf_path)
    if not pages:
        print(f"[HALUK VISUAL] Sayfa yok: {pdf_path}")
        return []

    client = _anthropic_client()
    page_results: List[Dict[str, Any]] = []
    for page_num, png in pages:
        try:
            result = analyze_page_image(client, png, page_num)
            charts = result.get("charts") or []
            if charts:
                print(
                    f"[HALUK VISUAL] sayfa {page_num}: "
                    + ", ".join(
                        f"{c.get('symbol', '?')} S={len(c.get('supports') or [])} R={len(c.get('resistances') or [])}"
                        for c in charts
                        if isinstance(c, dict)
                    )
                )
            page_results.append(result)
        except Exception as exc:
            print(f"[HALUK VISUAL] sayfa {page_num} hata: {exc}")

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
