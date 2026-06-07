# -*- coding: utf-8 -*-
"""Yayın Özeti videosu — transkript, Claude analiz, Telegram özet, tahmin kaydı."""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.getenv("HALUK_YAYIN_MODEL", os.getenv("HALUK_ARCHIVE_MODEL", "claude-sonnet-4-6"))
TR_TZ = timezone(timedelta(hours=3))

_claude = None
_claude_lock = threading.Lock()


def _get_claude():
    global _claude
    with _claude_lock:
        if _claude is None:
            import anthropic
            _claude = anthropic.Anthropic()
        return _claude


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def analyze_yayin_transcript(transcript: str, title: str, date_str: str) -> Dict[str, Any]:
    """Claude ile yayın özeti + tarihli tahminler."""
    client = _get_claude()
    prompt = (
        "Haluk Hoca kripto yayın özeti transkriptini analiz et. Sadece JSON döndür:\n"
        "{\n"
        '  "bullets": ["önemli nokta 1", "önemli nokta 2", "önemli nokta 3"],\n'
        '  "dated_prediction": "tarihli tahmin/uyarı metni veya null",\n'
        '  "highlight_coin": "BTC veya null",\n'
        '  "predictions": [\n'
        '    {"tahmin": "ne olacağı", "hedef_tarih": "YYYY-MM-DD"}\n'
        "  ]\n"
        "}\n"
        "predictions: Hoca belirli bir tarihte bir şey olacağını söylediyse ekle. "
        "Yoksa boş dizi.\n\n"
        f"Başlık: {title}\nTarih: {date_str}\n\nTranskript:\n{transcript[:12000]}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _parse_json(resp.content[0].text)
    bullets = [str(b).strip() for b in (data.get("bullets") or []) if str(b).strip()][:6]
    if len(bullets) < 3:
        while len(bullets) < 3:
            bullets.append("—")
    dp = data.get("dated_prediction")
    dated_prediction = str(dp).strip() if dp and str(dp).lower() not in ("null", "none", "") else None
    hc = data.get("highlight_coin")
    highlight_coin = str(hc).strip().upper().replace("USDT", "") if hc and str(hc).lower() not in ("null", "none", "") else None
    predictions = data.get("predictions") or []
    return {
        "bullets": bullets[:3],
        "dated_prediction": dated_prediction,
        "highlight_coin": highlight_coin,
        "predictions": predictions if isinstance(predictions, list) else [],
    }


def format_telegram_summary(date_str: str, analysis: Dict[str, Any]) -> str:
    bullets = analysis.get("bullets") or ["—", "—", "—"]
    lines = [
        "📺 YAYIM ÖZETİ",
        f"Tarih: {date_str}",
        "Önemli noktalar:",
        "",
        bullets[0],
        bullets[1],
        bullets[2],
        "",
        f"Tarihli tahmin/uyarı: {analysis.get('dated_prediction') or '—'}",
        f"Öne çıkan coin: {analysis.get('highlight_coin') or '—'}",
    ]
    return "\n".join(lines)


def send_yayin_summary(text: str) -> bool:
    try:
        from mina_dashboard_settings import load_settings
        if not load_settings().get("telegramNotify", True):
            return False
    except Exception:
        pass
    try:
        from tools.telegram_bot import send_notification
        send_notification(text)
        return True
    except Exception as exc:
        print(f"[YAYIN ÖZET] Telegram hatası: {exc}")
        return False


async def process_yayin_ozeti_video(
    client,
    channel_id: int,
    message_id: int,
    *,
    title: str = "",
    date_str: str = "",
) -> bool:
    """Yayın özeti videosunu transkript et, analiz et, Telegram gönder."""
    from signal_bot.haluk_predictions import (
        insert_predictions_batch,
        mark_summary_sent,
        summary_already_sent,
    )
    from signal_bot.haluk_video_transcriber import (
        download_and_transcribe_message,
        has_transcript,
        read_transcript,
    )

    if summary_already_sent(message_id):
        print(f"[YAYIN ÖZET] ATLA {message_id} — özet zaten gönderildi")
        return False

    if has_transcript(message_id):
        transcript = read_transcript(message_id) or ""
    else:
        transcript = await download_and_transcribe_message(
            client,
            channel_id,
            message_id,
            title=title,
            date_str=date_str,
            category="Yayın Özeti",
        )

    if not transcript or len(transcript) < 20:
        print(f"[YAYIN ÖZET] Transkript yetersiz: {message_id}")
        return False

    analysis = analyze_yayin_transcript(transcript, title, date_str)
    msg = format_telegram_summary(date_str, analysis)
    send_yayin_summary(msg)

    insert_predictions_batch(
        analysis.get("predictions") or [],
        message_id=message_id,
        tarih=date_str,
    )
    mark_summary_sent(message_id, date_str)
    print(f"[YAYIN ÖZET] Gönderildi msg_id={message_id}")
    return True


def schedule_yayin_ozeti(client, channel_id: int, message_id: int, title: str, date_str: str) -> None:
    """Listener'dan fire-and-forget."""

    async def _run():
        try:
            await process_yayin_ozeti_video(
                client, channel_id, message_id, title=title, date_str=date_str,
            )
        except Exception as exc:
            print(f"[YAYIN ÖZET] Hata msg_id={message_id}: {exc}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(process_yayin_ozeti_video(
            client, channel_id, message_id, title=title, date_str=date_str,
        ))
