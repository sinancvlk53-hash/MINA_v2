# -*- coding: utf-8 -*-
"""Haluk video listesi — kategori kuralları (öncelik sırasıyla)."""
from __future__ import annotations

from typing import Dict, List, Tuple

# İlk eşleşen kategori kazanır (daha spesifik olanlar üstte)
CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("Tahmin Et Serisi", ["tahmin"]),
    ("Yayın Özeti", ["yayın özeti", "yayin ozeti", "özet", "ozet"]),
    ("Fib Serisi", ["fibonacci", "fib"]),
    ("Upbit/Binance Listelemeleri", ["upbit", "listing", "listeleme"]),
    ("Piyasa Videoları", ["piyasa", "market", "btc", "bitcoin"]),
    ("Teknik Analiz", ["teknik analiz", "analiz"]),
    ("Eğitim Videoları", ["eğitim", "egitim", "ders", "nasıl", "nasil"]),
    ("Al Sat Kararları", ["al sat", "alım", "alim", "satım", "satim", "işlem", "islem"]),
]

CATEGORY_ORDER: List[str] = [c[0] for c in CATEGORY_RULES] + ["Diğer"]


def _normalize(text: str) -> str:
    t = (text or "").lower()
    for a, b in (("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c")):
        t = t.replace(a, b)
    return t


def categorize_video(title: str, description: str) -> str:
    blob = _normalize(f"{title} {description}")
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if _normalize(kw) in blob:
                return cat
    return "Diğer"


def category_stats(videos: List[dict]) -> Dict[str, int]:
    stats: Dict[str, int] = {c: 0 for c in CATEGORY_ORDER}
    for v in videos:
        cat = v.get("category") or "Diğer"
        stats[cat] = stats.get(cat, 0) + 1
    return stats
