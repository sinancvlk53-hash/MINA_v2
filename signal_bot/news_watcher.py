# -*- coding: utf-8 -*-
"""Kripto haber izleyici — CryptoPanic/CryptoCompare + Claude risk skoru."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("MINA_DATA_ROOT", _ROOT)
STATE_PATH = os.path.join(ROOT, "signal_bot", "news_watcher_state.json")
WATCH_INTERVAL_SEC = int(os.getenv("NEWS_WATCH_SEC", str(30 * 60)))
RISK_ALERT_THRESHOLD = int(os.getenv("NEWS_RISK_ALERT", "7"))

NEWS_ALARM = ("FLASHCRASH", "MAYIN TARLASI", "BALINA SATIŞI", "BALINA SATISI")


def _default_risk_result(reason: str = "") -> Dict[str, Any]:
    return {
        "score": 0,
        "summary": reason or "analiz yapılamadı",
        "alert": False,
        "keywords": [],
        "headlines": [],
    }


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        print(f"[NEWS WATCHER] state yazma hatası: {exc}")


def fetch_news(limit: int = 20) -> List[dict]:
    """Son kripto haberlerini çek. Hata → []."""
    try:
        items: List[dict] = []
        token = os.getenv("CRYPTOPANIC_API_KEY", "").strip()
        headers = {"User-Agent": "MINA-news/1.0"}

        if token:
            url = "https://cryptopanic.com/api/v1/posts/"
            params = {
                "auth_token": token,
                "public": "true",
                "kind": "news",
                "filter": "important",
            }
            resp = requests.get(url, params=params, timeout=10, headers=headers)
            resp.raise_for_status()
            for row in resp.json().get("results", [])[:limit]:
                items.append({
                    "id": str(row.get("id", "")),
                    "title": str(row.get("title") or "").strip(),
                    "url": row.get("url", ""),
                    "published": row.get("published_at", ""),
                    "source": (row.get("source") or {}).get("title", ""),
                })
        else:
            url = "https://min-api.cryptocompare.com/data/v2/news/"
            params = {"lang": "EN", "categories": "BTC,ETH,Trading,Blockchain,Exchange"}
            resp = requests.get(url, params=params, timeout=10, headers=headers)
            resp.raise_for_status()
            for row in resp.json().get("Data", [])[:limit]:
                src = row.get("source_info") or {}
                items.append({
                    "id": str(row.get("id", "")),
                    "title": str(row.get("title") or "").strip(),
                    "url": row.get("url", ""),
                    "published": row.get("published_on", ""),
                    "source": src.get("name", "") if isinstance(src, dict) else "",
                })
        return [x for x in items if x.get("title")]
    except Exception as exc:
        print(f"[NEWS WATCHER] fetch_news hatası: {exc}")
        return []


def analyze_news_risk(headlines: List[dict]) -> Dict[str, Any]:
    """Haber başlıklarından risk skoru üret. Hata → score=0."""
    if not headlines:
        return _default_risk_result("haber yok")

    titles = [str(h.get("title") or "").strip() for h in headlines if h.get("title")]
    if not titles:
        return _default_risk_result("başlık yok")

    try:
        blob = " ".join(titles).upper()
        for kw in NEWS_ALARM:
            if kw in blob:
                return {
                    "score": 10,
                    "summary": f"Haber alarmı tetiklendi: {kw}",
                    "alert": True,
                    "keywords": [kw],
                    "headlines": titles[:5],
                }

        import anthropic

        client = anthropic.Anthropic()
        listing = "\n".join(f"- {t}" for t in titles[:15])
        prompt = f"""Kripto piyasası için aşağıdaki son haber başlıklarını analiz et.

Başlıklar:
{listing}

Sadece geçerli JSON döndür:
{{"score": 0, "summary": "1 cümle", "alert": false, "keywords": []}}

score: 0=sakin, 10=acil risk (hack, regülasyon yasağı, borsa iflas, flash crash)
alert: score>=7 veya ani piyasa riski varsa true"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (
            resp.content[0].text.strip()
            .lstrip("```json")
            .lstrip("```")
            .rstrip("```")
            .strip()
        )
        data = json.loads(raw)
        score = max(0, min(10, int(data.get("score", 0))))
        alert = bool(data.get("alert", False)) or score >= RISK_ALERT_THRESHOLD
        return {
            "score": score,
            "summary": str(data.get("summary") or ""),
            "alert": alert,
            "keywords": list(data.get("keywords") or []),
            "headlines": titles[:5],
        }
    except Exception as exc:
        print(f"[NEWS WATCHER] analyze_news_risk hatası: {exc}")
        return _default_risk_result(str(exc))


def run_news_watcher() -> Dict[str, Any]:
    """Tek haber tarama döngüsü — hata sistemi kilitlemez."""
    try:
        state = _read_json(STATE_PATH, {"seen_ids": []})
        seen = set(state.get("seen_ids") or [])

        news = fetch_news()
        new_items = [n for n in news if n.get("id") and n["id"] not in seen]
        analyze_items = new_items[:10] if new_items else news[:10]

        risk = analyze_news_risk(analyze_items)
        score = int(risk.get("score", 0))
        should_alert = bool(risk.get("alert")) or score >= RISK_ALERT_THRESHOLD

        result: Dict[str, Any] = {
            "score": score,
            "summary": risk.get("summary", ""),
            "alert": should_alert,
            "keywords": risk.get("keywords", []),
            "headlines": risk.get("headlines", []),
            "new_count": len(new_items),
            "fetched": len(news),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        for item in news:
            item_id = item.get("id")
            if item_id:
                seen.add(str(item_id))
        state["seen_ids"] = sorted(seen)[-500:]
        state["last_result"] = result
        _write_json(STATE_PATH, state)

        if should_alert and new_items:
            try:
                from mina_motor_telegram import send_telegram

                lines = "\n".join(f"• {t}" for t in result["headlines"][:5])
                send_telegram(
                    f"🚨 *Haber Risk Alarmı* ({score}/10)\n"
                    f"{result['summary']}\n\n{lines}"
                )
            except Exception as exc:
                print(f"[NEWS WATCHER] Telegram hatası: {exc}")

        print(
            f"[NEWS WATCHER] score={score} new={len(new_items)} "
            f"fetched={len(news)} alert={should_alert}"
        )
        return result
    except Exception as exc:
        print(f"[NEWS WATCHER] run_news_watcher hatası: {exc}")
        return {
            "score": 0,
            "summary": str(exc),
            "alert": False,
            "keywords": [],
            "headlines": [],
            "error": str(exc),
        }


def watcher_cycle() -> Dict[str, Any]:
    """Döngü güvenli sarmalayıcı."""
    try:
        return run_news_watcher()
    except Exception as exc:
        print(f"[NEWS WATCHER] watcher_cycle hatası: {exc}")
        return _default_risk_result(str(exc)) | {"error": str(exc)}


def main() -> None:
    print(f"[NEWS WATCHER] Başladı — döngü {WATCH_INTERVAL_SEC // 60} dk")
    while True:
        try:
            watcher_cycle()
        except Exception as exc:
            print(f"[NEWS WATCHER] döngü hatası: {exc}")
        time.sleep(WATCH_INTERVAL_SEC)


if __name__ == "__main__":
    main()
