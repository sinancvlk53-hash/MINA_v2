#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haluk Hoca Telegram kanalı — tüm video mesajlarını listele.
session_ht.session kullanır.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import DocumentAttributeVideo

OUT_JSON = os.path.join(_ROOT, "signal_bot", "history", "haluk_video_list.json")
OUT_MD = os.path.join(_ROOT, "signal_bot", "history", "haluk_video_list.md")

TR_TZ = timezone(timedelta(hours=3))

from signal_bot.haluk_video_categories import (
    CATEGORY_ORDER,
    categorize_video,
    category_stats,
)


def _env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize(text: str) -> str:
    t = (text or "").lower()
    for a, b in (("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c")):
        t = t.replace(a, b)
    return t


def _is_video_message(msg) -> bool:
    if getattr(msg, "video", None):
        return True
    if getattr(msg, "video_note", None):
        return True
    doc = getattr(msg, "document", None)
    if not doc:
        return False
    mime = getattr(doc, "mime_type", "") or ""
    if mime.startswith("video/"):
        return True
    for attr in getattr(doc, "attributes", []) or []:
        if isinstance(attr, DocumentAttributeVideo):
            return True
    return False


def _video_duration_sec(msg) -> Optional[int]:
    vid = getattr(msg, "video", None)
    if vid and getattr(vid, "duration", None):
        return int(vid.duration)
    vn = getattr(msg, "video_note", None)
    if vn and getattr(vn, "duration", None):
        return int(vn.duration)
    doc = getattr(msg, "document", None)
    if doc:
        for attr in getattr(doc, "attributes", []) or []:
            if isinstance(attr, DocumentAttributeVideo) and getattr(attr, "duration", None):
                return int(attr.duration)
    return None


def _format_duration(seconds: Optional[int]) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _message_text(msg) -> str:
    return (msg.text or msg.message or "").strip()


def _title_from_text(text: str) -> str:
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    title = lines[0]
    title = re.sub(r"\s+", " ", title)
    return title[:500]


def categorize(title: str, description: str) -> str:
    return categorize_video(title, description)


def _fmt_ts(dt) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TR_TZ).strftime("%Y-%m-%d %H:%M")


def write_markdown(videos: List[Dict[str, Any]], path: str) -> None:
    stats = category_stats(videos)
    grouped: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORY_ORDER}
    for v in videos:
        cat = v.get("category") or "Diğer"
        grouped.setdefault(cat, []).append(v)

    lines = [
        "# Haluk Hoca — Video Listesi",
        "",
        f"**Toplam:** {len(videos)} video",
        f"**Oluşturulma:** {datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M')} (TR)",
        "",
        "## Grup İstatistikleri",
        "",
        "| Grup | Adet |",
        "|------|------|",
    ]
    for cat in CATEGORY_ORDER:
        lines.append(f"| {cat} | {stats.get(cat, 0)} |")
    lines.append("")

    for cat in CATEGORY_ORDER:
        items = grouped.get(cat) or []
        lines.append(f"## {cat} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_Video yok._")
            lines.append("")
            continue
        for v in items:
            title = v.get("title") or "(başlıksız)"
            lines.append(
                f"- **#{v['message_id']}** · {v.get('date', '—')} · "
                f"{v.get('duration_display', '—')} · {title}"
            )
            desc = (v.get("description") or "").strip()
            if desc and desc != title:
                preview = desc.replace("\n", " ")[:200]
                if len(desc) > 200:
                    preview += "…"
                lines.append(f"  - {preview}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def fetch_all_videos(client, channel_id: int) -> List[Dict[str, Any]]:
    videos: List[Dict[str, Any]] = []
    count = 0
    async for msg in client.iter_messages(channel_id, limit=None):
        if not _is_video_message(msg):
            continue
        text = _message_text(msg)
        title = _title_from_text(text)
        dur = _video_duration_sec(msg)
        entry = {
            "message_id": msg.id,
            "date": _fmt_ts(msg.date),
            "date_utc": msg.date.replace(tzinfo=timezone.utc).isoformat() if msg.date else None,
            "duration_sec": dur,
            "duration_display": _format_duration(dur),
            "title": title,
            "description": text[:2000] if text else "",
            "category": categorize(title, text),
            "has_video_note": bool(getattr(msg, "video_note", None)),
        }
        videos.append(entry)
        count += 1
        if count % 50 == 0:
            print(f"  ... {count} video", flush=True)
        if count % 200 == 0:
            await asyncio.sleep(0.5)
    videos.sort(key=lambda x: x.get("date_utc") or "", reverse=True)
    return videos


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    api_id = _env_int("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    channel_id = _env_int("TELEGRAM_HALUK_CHANNEL_ID")
    session = os.path.join(_ROOT, os.getenv("TELEGRAM_HALUK_SESSION", "session_ht").strip())

    if not api_id or not api_hash or not channel_id:
        print("TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_HALUK_CHANNEL_ID eksik")
        return 1

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

    client = TelegramClient(session, api_id, api_hash)
    await client.start()
    print(f"Kanal taranıyor: {channel_id}")

    try:
        videos = await fetch_all_videos(client, channel_id)
    except FloodWaitError as exc:
        print(f"FloodWait {exc.seconds}s — bekleniyor...")
        await asyncio.sleep(exc.seconds + 1)
        videos = await fetch_all_videos(client, channel_id)
    finally:
        await client.disconnect()

    payload = {
        "channel_id": channel_id,
        "total": len(videos),
        "generated_at": datetime.now(TR_TZ).isoformat(),
        "videos": videos,
        "by_category": category_stats(videos),
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    write_markdown(videos, OUT_MD)

    print(f"\nToplam: {len(videos)} video")
    for cat in CATEGORY_ORDER:
        print(f"  {cat}: {payload['by_category'].get(cat, 0)}")
    print(f"JSON: {OUT_JSON}")
    print(f"MD:   {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
