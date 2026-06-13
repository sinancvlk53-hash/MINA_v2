# -*- coding: utf-8 -*-
"""Upbit listeleme habercisi — site duyuruları + @Official_Upbit Twitter."""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(ROOT, "signal_bot", "upbit_listing_reporter_state.json")

WATCH_INTERVAL_SEC = int(os.environ.get("UPBIT_LISTING_WATCH_SEC", "30"))
NOTICE_PROBE_START = int(os.environ.get("UPBIT_NOTICE_PROBE_START", "7000"))
NOTICE_MAX_SCAN = int(os.environ.get("UPBIT_NOTICE_MAX_SCAN", "8"))

UPBIT_NOTICE_URL = "https://upbit.com/service_center/notice?id={id}"
UPBIT_MARKET_URL = "https://api.upbit.com/v1/market/all"
GENERIC_TITLE = "업비트(Upbit)"

TWITTER_RSS_URLS = [
    u.strip()
    for u in os.environ.get(
        "UPBIT_TWITTER_RSS_URLS",
        "https://nitter.net/Official_Upbit/rss,https://nitter.privacydev.net/Official_Upbit/rss",
    ).split(",")
    if u.strip()
]

LISTING_KEYWORDS = (
    "상장", "listing", "listeleme", "마켓", "거래지원", "디지털 자산", "krw", "신규", "추가",
    "market support", "trading support",
)

TR_TZ = timezone(timedelta(hours=3))

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_state() -> Dict[str, Any]:
    return _read_json(STATE_PATH, {
        "seeded": False,
        "last_notice_id": 0,
        "seen_notice_ids": [],
        "known_krw_markets": [],
        "seen_tweet_guids": [],
    })


def save_state(data: Dict[str, Any]) -> None:
    data["updatedAt"] = int(time.time())
    _write_json(STATE_PATH, data)


def fmt_now() -> str:
    return datetime.now(tz=TR_TZ).strftime("%Y-%m-%d %H:%M")


def is_listing_text(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in LISTING_KEYWORDS)


def extract_coins(text: str) -> List[str]:
    upper = (text or "").upper()
    paren = re.findall(r"\(([A-Z0-9]{2,12})\)", upper)
    usdt = [c.replace("USDT", "") for c in re.findall(r"\b([A-Z0-9]{2,12})USDT\b", upper)]
    tags = re.findall(r"#([A-Z0-9]{2,12})\b", upper)
    skip = {"UPBIT", "KRW", "BTC", "USDT", "THE", "AND", "FOR", "NEW", "RT"}
    out: List[str] = []
    for c in paren + usdt + tags:
        if c not in skip and c not in out:
            out.append(c)
    return out[:5]


def translate_to_turkish(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "—"
    if not re.search(r"[\u3131-\u318E\uAC00-\uD7A3]", text):
        return text
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=os.getenv("UPBIT_TRANSLATE_MODEL", "claude-sonnet-4-6"),
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "Aşağıdaki Korece kripto borsa duyurusunu kısa ve net Türkçe'ye çevir. "
                    "Sadece çeviri metnini döndür.\n\n" + text[:1500]
                ),
            }],
        )
        return (resp.content[0].text or text).strip()
    except Exception as exc:
        print(f"[UPBIT LISTING] Çeviri hatası: {exc}")
        return text


def telegram_enabled() -> bool:
    try:
        from mina_dashboard_settings import load_settings
        return bool(load_settings().get("telegramNotify", True))
    except Exception:
        return True


def send_upbit_listing_telegram(coin: str, source: str, summary: str, when: str) -> bool:
    if not telegram_enabled():
        return False
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    coin_s = coin or "—"
    text = (
        "🔔 UPBİT LİSTELEME!\n"
        f"Coin: {coin_s}\n"
        f"Kaynak: {source}\n"
        f"Özet: {summary}\n"
        f"Saat: {when}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        return True
    except Exception as exc:
        print(f"[UPBIT LISTING] Telegram hatası: {exc}")
        return False


def fetch_notice_title(notice_id: int) -> Optional[str]:
    for attempt in range(2):
        try:
            r = requests.get(
                UPBIT_NOTICE_URL.format(id=notice_id),
                headers=HTTP_HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            m = re.search(r"<title>([^<]+)</title>", r.text)
            if not m:
                continue
            title = m.group(1).strip()
            if not title or title == GENERIC_TITLE:
                return None
            return title
        except Exception:
            if attempt == 0:
                time.sleep(0.3)
    return None


def bootstrap_notice_id_from_rss(items: Optional[List[Dict[str, str]]] = None) -> int:
    rows = items if items is not None else fetch_twitter_items()
    best = 0
    for it in rows:
        blob = f"{it.get('title', '')} {it.get('description', '')}"
        for m in re.finditer(r"notice\?id=(\d+)", blob):
            best = max(best, int(m.group(1)))
    return best


def title_from_rss_for_notice(notice_id: int, items: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    needle = f"notice?id={notice_id}"
    rows = items if items is not None else fetch_twitter_items()
    for it in rows:
        blob = f"{it.get('title', '')} {it.get('description', '')}"
        if needle not in blob:
            continue
        title = re.sub(r"\s+", " ", it.get("title", "")).strip()
        title = re.sub(r"^R to @Official_Upbit:\s*", "", title)
        if title:
            return title
    return None


def resolve_notice_title(notice_id: int, items: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    return fetch_notice_title(notice_id) or title_from_rss_for_notice(notice_id, items)


def find_latest_notice_id(items: Optional[List[Dict[str, str]]] = None, start: int = NOTICE_PROBE_START) -> int:
    rss_id = bootstrap_notice_id_from_rss(items)
    probe = max(start, rss_id, 1)
    if not resolve_notice_title(probe, items):
        while probe > 1 and not resolve_notice_title(probe, items):
            probe -= 25
            time.sleep(0.05)
    if not resolve_notice_title(probe, items):
        return rss_id
    hi = probe
    while resolve_notice_title(hi + 1, items):
        hi += 1
        time.sleep(0.06)
    return hi


def check_new_notices(state: Dict[str, Any], twitter_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    last_id = int(state.get("last_notice_id") or 0)
    seen: Set[int] = set(int(x) for x in (state.get("seen_notice_ids") or []))

    if not state.get("seeded") or last_id <= 0:
        last_id = find_latest_notice_id(twitter_items)
        if last_id <= 0:
            last_id = bootstrap_notice_id_from_rss(twitter_items)
        state["last_notice_id"] = last_id
        state["seeded"] = True
        if last_id > 0:
            seen.add(last_id)
        state["seen_notice_ids"] = sorted(seen)[-500:]
        print(f"[UPBIT LISTING] Notice seed: son id={last_id} (alarm yok)")
        return alerts

    rss_max = bootstrap_notice_id_from_rss(twitter_items)
    scan_upto = max(last_id + NOTICE_MAX_SCAN, rss_max)
    new_max = last_id
    for nid in range(last_id + 1, scan_upto + 1):
        title = resolve_notice_title(nid, twitter_items)
        if not title:
            if nid <= rss_max:
                continue
            break
        new_max = nid
        if nid in seen:
            continue
        if not is_listing_text(title):
            seen.add(nid)
            continue
        coins = extract_coins(title)
        summary = translate_to_turkish(title)
        alerts.append({
            "coin": ", ".join(coins) if coins else "—",
            "source": "Upbit site",
            "summary": summary,
            "when": fmt_now(),
            "notice_id": nid,
            "raw": title,
        })
        seen.add(nid)
        time.sleep(0.08)

    state["last_notice_id"] = new_max
    state["seen_notice_ids"] = sorted(seen)[-500:]
    return alerts


def fetch_krw_markets() -> Set[str]:
    r = requests.get(UPBIT_MARKET_URL, headers=HTTP_HEADERS, timeout=20)
    r.raise_for_status()
    return {
        str(row.get("market") or "")
        for row in r.json()
        if str(row.get("market", "")).startswith("KRW-")
    }


def check_new_krw_markets(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    current = fetch_krw_markets()
    known = set(state.get("known_krw_markets") or [])

    if not state.get("seeded_markets"):
        state["known_krw_markets"] = sorted(current)
        state["seeded_markets"] = True
        print(f"[UPBIT LISTING] KRW market seed: {len(current)} çift (alarm yok)")
        return alerts

    new_markets = sorted(current - known)
    for market in new_markets:
        coin = market.replace("KRW-", "")
        title = f"{coin} KRW market added on Upbit"
        alerts.append({
            "coin": coin,
            "source": "Upbit site",
            "summary": translate_to_turkish(title),
            "when": fmt_now(),
            "market": market,
        })

    if new_markets:
        state["known_krw_markets"] = sorted(current)
    return alerts


def _parse_rss_items(xml_text: str) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    out: List[Dict[str, str]] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or item.findtext("link") or title).strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        out.append({"title": title, "guid": guid, "pubDate": pub, "description": desc})
    return out


def fetch_twitter_items() -> List[Dict[str, str]]:
    for url in TWITTER_RSS_URLS:
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
            if r.status_code != 200 or "<rss" not in r.text[:300]:
                continue
            items = _parse_rss_items(r.text)
            if items:
                return items
        except Exception as exc:
            print(f"[UPBIT LISTING] Twitter RSS hatası ({url}): {exc}")
    return []


def check_twitter(state: Dict[str, Any], items: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    seen = set(state.get("seen_tweet_guids") or [])
    rows = items if items is not None else fetch_twitter_items()

    if not state.get("seeded_twitter"):
        for it in rows[:20]:
            seen.add(it["guid"])
        state["seen_tweet_guids"] = list(seen)[-300:]
        state["seeded_twitter"] = True
        print(f"[UPBIT LISTING] Twitter seed: {len(seen)} tweet (alarm yok)")
        return alerts

    for it in rows:
        guid = it["guid"]
        if guid in seen:
            continue
        text = f"{it.get('title', '')} {it.get('description', '')}"
        if "상장" not in text and "listing" not in text.lower():
            seen.add(guid)
            continue
        if "R to @" in it.get("title", ""):
            seen.add(guid)
            continue
        coins = extract_coins(text)
        summary = translate_to_turkish(re.sub(r"<[^>]+>", " ", it.get("title", "")))
        alerts.append({
            "coin": ", ".join(coins) if coins else "—",
            "source": "Twitter",
            "summary": summary,
            "when": it.get("pubDate") or fmt_now(),
            "guid": guid,
        })
        seen.add(guid)

    state["seen_tweet_guids"] = list(seen)[-300:]
    return alerts


def dispatch_alerts(alerts: List[Dict[str, Any]]) -> int:
    sent = 0
    for a in alerts:
        if send_upbit_listing_telegram(a.get("coin", "—"), a["source"], a["summary"], a["when"]):
            sent += 1
            print(f"[UPBIT LISTING] Telegram: {a.get('coin')} @ {a['source']}")
    return sent


def watcher_cycle() -> Tuple[int, int]:
    state = load_state()
    twitter_items = fetch_twitter_items()
    alerts: List[Dict[str, Any]] = []
    alerts.extend(check_new_notices(state, twitter_items))
    alerts.extend(check_new_krw_markets(state))
    alerts.extend(check_twitter(state, twitter_items))

    # Dedup by coin+source+summary prefix
    uniq: List[Dict[str, Any]] = []
    keys: Set[str] = set()
    for a in alerts:
        key = f"{a.get('source')}|{a.get('coin')}|{(a.get('summary') or '')[:80]}"
        if key in keys:
            continue
        keys.add(key)
        uniq.append(a)

    sent = dispatch_alerts(uniq)
    save_state(state)

    # AUTO_TRADE kapalı — SHORT pipeline devre dışı, yalnızca dispatch_alerts Telegram.

    return len(uniq), sent
