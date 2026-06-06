#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haluk Hoca son 100 mesaj analizi — Claude API ile sınıflandırma ve istatistik.

Kaynak önceliği:
  1. signal_bot/signals_log.txt  ([HALUK] İLK MESAJ satırları)
  2. signal_bot/history/ht_history.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

SIGNALS_LOG = os.path.join(ROOT, "signal_bot", "signals_log.txt")
HT_HISTORY_JSON = os.path.join(ROOT, "signal_bot", "history", "ht_history.json")
HT_HISTORY_TXT = os.path.join(ROOT, "signal_bot", "history", "ht_history.txt")
BATCH_SIZE = 10
MODEL = os.getenv("HALUK_ANALYSIS_MODEL", "claude-sonnet-4-6")


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def load_from_signals_log(limit: int = 100) -> List[str]:
    if not os.path.isfile(SIGNALS_LOG):
        return []
    pattern = re.compile(r"\[HALUK\]\s+(?:İLK|ILK)\s+MESAJ.*?metin:\s*(.+)$", re.IGNORECASE)
    found: List[str] = []
    with open(SIGNALS_LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pattern.search(line.strip())
            if m:
                found.append(m.group(1).strip())
    return _dedupe_keep_order(found)[-limit:]


def load_from_ht_history_json(limit: int = 100) -> List[str]:
    if not os.path.isfile(HT_HISTORY_JSON):
        return []
    data = json.load(open(HT_HISTORY_JSON, encoding="utf-8"))
    texts = [
        str(x.get("metin") or "").strip()
        for x in data
        if str(x.get("gonderen", "")).strip() in ("HT VIP BTC", "Haluk TATAR")
    ]
    texts = [t for t in texts if t]
    return _dedupe_keep_order(texts)[-limit:]


def load_from_ht_history_txt(limit: int = 100) -> List[str]:
    if not os.path.isfile(HT_HISTORY_TXT):
        return []
    pattern = re.compile(r"^\[[^\]]+\]\s+\[HT VIP BTC\]\s+(.+)$")
    found: List[str] = []
    with open(HT_HISTORY_TXT, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                found.append(m.group(1).strip())
    return _dedupe_keep_order(found)[-limit:]


def load_haluk_messages(limit: int = 100) -> tuple[List[str], str]:
    for loader, name in (
        (load_from_signals_log, "signals_log.txt"),
        (load_from_ht_history_json, "ht_history.json"),
        (load_from_ht_history_txt, "ht_history.txt"),
    ):
        msgs = loader(limit)
        if msgs:
            return msgs[-limit:], name
    return [], "yok"


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    data = json.loads(text)
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list):
        raise ValueError("Claude yanıtı liste değil")
    return data


def analyze_batch(client, batch: List[str], offset: int) -> List[Dict[str, Any]]:
    numbered = "\n".join(f"{offset + i}: {msg[:800]}" for i, msg in enumerate(batch))
    prompt = f"""Haluk Hoca (kripto eğitmeni) Telegram mesajlarını analiz et.

Her mesaj için JSON nesnesi döndür. Tüm mesajları tek JSON array olarak ver.

Alanlar:
- i: mesaj indeksi (aşağıdaki numara)
- category: "box_region" | "macro_comment" | "trade_signal" | "news_other"
  * box_region: kutu, bölge, destek, direnç, seviye, retest
  * macro_comment: TOTAL, OTHERS, BTC.D, genel piyasa/altcoin yorumu
  * trade_signal: açık Long/Short pozisyon önerisi veya giriş emri
  * news_other: haber, duyuru, sohbet, anket, yayın linki
- has_entry_price: boolean — somut giriş fiyatı/seviyesi var mı
- btc_eth_alt_split: boolean — BTC, ETH ve altcoin ayrımı yapılıyor mu
- coins: bahsedilen coin sembolleri (USDT'siz, büyük harf)
- al_coins: AL/Long önerilen coinler
- sat_coins: SAT/Short önerilen coinler

Sadece geçerli JSON array döndür, başka metin yazma.

Mesajlar:
{numbered}"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    return _parse_json_array(raw)


def aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    cat = Counter()
    entry_count = 0
    split_count = 0
    coin_mentions = Counter()
    al_coins = Counter()
    sat_coins = Counter()

    for row in results:
        cat[row.get("category", "news_other")] += 1
        if row.get("has_entry_price"):
            entry_count += 1
        if row.get("btc_eth_alt_split"):
            split_count += 1
        for c in row.get("coins") or []:
            sym = str(c).upper().replace("USDT", "").strip()
            if sym and sym not in ("TOTAL", "OTHERS", "BTC", "ETH"):
                coin_mentions[sym] += 1
            elif sym in ("BTC", "ETH"):
                coin_mentions[sym] += 1
        for c in row.get("al_coins") or []:
            sym = str(c).upper().replace("USDT", "").strip()
            if sym:
                al_coins[sym] += 1
        for c in row.get("sat_coins") or []:
            sym = str(c).upper().replace("USDT", "").strip()
            if sym:
                sat_coins[sym] += 1

    return {
        "box_region": cat.get("box_region", 0),
        "macro_comment": cat.get("macro_comment", 0),
        "trade_signal": cat.get("trade_signal", 0),
        "news_other": cat.get("news_other", 0),
        "entry_price_count": entry_count,
        "btc_eth_alt_split_count": split_count,
        "top_coins": coin_mentions.most_common(20),
        "top_al": al_coins.most_common(20),
        "top_sat": sat_coins.most_common(20),
    }


def print_report(source: str, total: int, stats: Dict[str, Any]) -> None:
    print("=" * 60)
    print("HALUK HOCA — SON 100 MESAJ ANALİZİ")
    print("=" * 60)
    print(f"Kaynak: {source}")
    print(f"Analiz edilen mesaj: {total}")
    print()
    print("--- Kategori dağılımı ---")
    print(f"  Kutu/bölge sinyali:     {stats['box_region']}")
    print(f"  Makro yorum:            {stats['macro_comment']}")
    print(f"  İşlem sinyali (Long/Short): {stats['trade_signal']}")
    print(f"  Haber/diğer:            {stats['news_other']}")
    print()
    print(f"  Giriş fiyatı/seviyesi olan: {stats['entry_price_count']}")
    print(f"  BTC/ETH/altcoin ayrımı olan: {stats['btc_eth_alt_split_count']}")
    print()
    print("--- En çok bahsedilen coinler ---")
    for sym, n in stats["top_coins"][:15]:
        print(f"  {sym}: {n}")
    if not stats["top_coins"]:
        print("  —")
    print()
    print("--- En çok AL/Long dediği coinler ---")
    for sym, n in stats["top_al"][:15]:
        print(f"  {sym}: {n}")
    if not stats["top_al"]:
        print("  —")
    print()
    print("--- En çok SAT/Short dediği coinler ---")
    for sym, n in stats["top_sat"][:15]:
        print(f"  {sym}: {n}")
    if not stats["top_sat"]:
        print("  —")
    print("=" * 60)


def main() -> None:
    messages, source = load_haluk_messages(100)
    if not messages:
        print("RED: Haluk mesajı bulunamadı (signals_log / history)")
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("RED: ANTHROPIC_API_KEY .env içinde tanımlı değil")
        sys.exit(1)

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    all_results: List[Dict[str, Any]] = []

    for start in range(0, len(messages), BATCH_SIZE):
        batch = messages[start : start + BATCH_SIZE]
        print(f"Claude analizi: {start + 1}-{start + len(batch)} / {len(messages)}...", flush=True)
        rows = analyze_batch(client, batch, start)
        all_results.extend(rows)

    stats = aggregate(all_results)
    print_report(source, len(messages), stats)


if __name__ == "__main__":
    main()
