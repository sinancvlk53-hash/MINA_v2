#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haluk Hoca Telegram kanalından Upbit videosunu indir → ses → Whisper transkript.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from telethon import TelegramClient

TARGET_PHRASE = "Upbit Listelemesinden Nasıl Para Kazanılıyor"
OUT_PATH = os.path.join(_ROOT, "signal_bot", "history", "upbit_video_transcript.txt")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")


def _env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _is_video_message(msg) -> bool:
    if getattr(msg, "video", None):
        return True
    doc = getattr(msg, "document", None)
    if not doc:
        return False
    mime = getattr(doc, "mime_type", "") or ""
    return mime.startswith("video/")


def _message_text(msg) -> str:
    return (msg.text or msg.message or "").strip()


async def find_target_video(client, channel_id: int):
    print(f"Kanal taranıyor: {channel_id}")
    # Önce Telegram arama
    try:
        async for msg in client.iter_messages(channel_id, search="Upbit Listelemesinden", limit=50):
            text = _message_text(msg)
            if TARGET_PHRASE.lower() not in text.lower():
                continue
            if _is_video_message(msg):
                print(f"Bulundu (search): id={msg.id} date={msg.date}")
                return msg
    except Exception as exc:
        print(f"Search atlandı: {exc}")

    # Geniş tarama — son 1 yıl
    since = datetime.now(timezone.utc) - timedelta(days=365)
    async for msg in client.iter_messages(channel_id, limit=2000):
        if msg.date and msg.date.replace(tzinfo=timezone.utc) < since:
            break
        text = _message_text(msg)
        if TARGET_PHRASE.lower() not in text.lower():
            continue
        if _is_video_message(msg):
            print(f"Bulundu (scan): id={msg.id} date={msg.date}")
            return msg
    return None


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(">>>", " ".join(cmd[:8]), ("..." if len(cmd) > 8 else ""))
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def video_to_wav(video_path: str, wav_path: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı")
    _run([
        ffmpeg, "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        wav_path,
    ])


def transcribe_whisper(wav_path: str) -> str:
    try:
        import whisper
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "openai-whisper"],
            check=True,
        )
        import whisper

    print(f"Whisper model yükleniyor: {WHISPER_MODEL}")
    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(wav_path, language="tr", fp16=False)
    text = (result.get("text") or "").strip()
    if not text:
        raise RuntimeError("Whisper boş transkript döndü")
    return text


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    api_id = _env_int("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    channel_id = _env_int("TELEGRAM_HALUK_CHANNEL_ID")
    session = os.path.join(_ROOT, os.getenv("TELEGRAM_HALUK_SESSION", "session_ht").strip())

    if not api_id or not api_hash or not channel_id:
        print("TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_HALUK_CHANNEL_ID eksik")
        return 1

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    client = TelegramClient(session, api_id, api_hash)
    await client.start()

    msg = await find_target_video(client, channel_id)
    if not msg:
        await client.disconnect()
        print(f"HATA: '{TARGET_PHRASE}' içeren video bulunamadı")
        return 2

    with tempfile.TemporaryDirectory(prefix="upbit_vid_") as tmp:
        video_path = await client.download_media(msg, file=os.path.join(tmp, "video"))
        await client.disconnect()

        if not video_path or not os.path.isfile(video_path):
            print("HATA: Video indirilemedi")
            return 3

        print(f"Video indirildi: {video_path} ({os.path.getsize(video_path) // 1024} KB)")
        wav_path = os.path.join(tmp, "audio.wav")
        video_to_wav(video_path, wav_path)
        print(f"Ses çıkarıldı: {wav_path}")

        transcript = transcribe_whisper(wav_path)
        header = (
            f"# Upbit Listelemesinden Nasıl Para Kazanılıyor?\n"
            f"# Telegram msg_id: {msg.id}\n"
            f"# Tarih: {msg.date}\n"
            f"# Model: whisper-{WHISPER_MODEL}\n"
            f"# Oluşturulma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.write(header + transcript + "\n")

        print(f"Transkript kaydedildi: {OUT_PATH} ({len(transcript)} karakter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
