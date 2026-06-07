#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haluk video toplu transkript — haluk_video_list.json, öncelik sırasıyla.
Kullanım: python scripts/transcribe_all_haluk_videos.py [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from telethon import TelegramClient

from signal_bot.haluk_video_transcriber import (
    _log,
    download_and_transcribe_message,
    has_transcript,
    load_video_list,
    sort_videos_by_priority,
)


def _env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


async def run(limit: int = 0) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    api_id = _env_int("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    channel_id = _env_int("TELEGRAM_HALUK_CHANNEL_ID")
    session_name = os.getenv("TELEGRAM_HALUK_TRANSCRIBE_SESSION", "session_ht_bulk").strip()
    session = os.path.join(_ROOT, session_name)

    if not api_id or not api_hash or not channel_id:
        _log("HATA: TELEGRAM_API_ID / HASH / HALUK_CHANNEL_ID eksik")
        return 1

    payload = load_video_list()
    videos = sort_videos_by_priority(payload.get("videos") or [])
    pending = [v for v in videos if not has_transcript(int(v["message_id"]))]
    if limit > 0:
        pending = pending[:limit]

    _log(f"Toplam {len(videos)} video, bekleyen {len(pending)}, işlenecek {len(pending)}")
    if not pending:
        _log("Tüm transkriptler mevcut.")
        return 0

    client = TelegramClient(session, api_id, api_hash)
    await client.start()
    ok = 0
    fail = 0
    try:
        for i, v in enumerate(pending, 1):
            mid = int(v["message_id"])
            try:
                await download_and_transcribe_message(
                    client,
                    channel_id,
                    mid,
                    title=v.get("title") or "",
                    date_str=v.get("date") or "",
                    category=v.get("category") or "",
                )
                ok += 1
            except Exception as exc:
                fail += 1
                _log(f"HATA {mid}: {exc}")
            if i % 10 == 0:
                _log(f"İlerleme {i}/{len(pending)} ok={ok} fail={fail}")
            await asyncio.sleep(1)
    finally:
        await client.disconnect()

    _log(f"Bitti — ok={ok} fail={fail} skip={len(videos) - len(pending)}")
    return 0 if fail == 0 else 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Max video sayısı (0=hepsi)")
    args = p.parse_args()
    return asyncio.run(run(limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
