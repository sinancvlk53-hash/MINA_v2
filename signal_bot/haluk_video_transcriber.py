# -*- coding: utf-8 -*-
"""Haluk video indirme + Whisper transkript yardımcıları."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

_ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from telethon.tl.types import DocumentAttributeVideo

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
VIDEO_LIST_JSON = os.path.join(_ROOT, "signal_bot", "history", "haluk_video_list.json")
TRANSCRIPT_DIR = os.path.join(_ROOT, "signal_bot", "history", "transcripts")
LOG_FILE = os.path.join(_ROOT, "signal_bot", "history", "transcribe_all.log")

TRANSCRIBE_PRIORITY = [
    "Eğitim Videoları",
    "Teknik Analiz",
    "Fib Serisi",
    "Tahmin Et Serisi",
    "Al Sat Kararları",
    "Piyasa Videoları",
    "Yayın Özeti",
    "Upbit/Binance Listelemeleri",
    "Diğer",
]

TR_TZ = timezone(timedelta(hours=3))


def transcript_path(message_id: int) -> str:
    return os.path.join(TRANSCRIPT_DIR, f"{message_id}.txt")


def has_transcript(message_id: int) -> bool:
    p = transcript_path(message_id)
    if not os.path.isfile(p):
        return False
    try:
        return os.path.getsize(p) > 50
    except OSError:
        return False


def read_transcript(message_id: int) -> Optional[str]:
    p = transcript_path(message_id)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None
    # Header satırlarını atla (# ile başlayan)
    lines = []
    for ln in raw.splitlines():
        if ln.startswith("#"):
            continue
        lines.append(ln)
    text = "\n".join(lines).strip()
    return text or None


def _log(msg: str) -> None:
    line = f"[{datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def title_from_text(text: str) -> str:
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    return re.sub(r"\s+", " ", lines[0])[:500]


def is_video_message(msg) -> bool:
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


def video_to_wav(video_path: str, wav_path: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı")
    subprocess.run(
        [ffmpeg, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path],
        check=True,
        capture_output=True,
    )


def transcribe_whisper(wav_path: str, model_name: Optional[str] = None) -> str:
    model_name = model_name or WHISPER_MODEL
    try:
        import whisper
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "openai-whisper"], check=True)
        import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(wav_path, language="tr", fp16=False)
    text = (result.get("text") or "").strip()
    if not text:
        raise RuntimeError("Whisper boş transkript döndü")
    return text


def save_transcript(
    message_id: int,
    transcript: str,
    *,
    title: str = "",
    date_str: str = "",
    category: str = "",
) -> str:
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    path = transcript_path(message_id)
    header = (
        f"# message_id: {message_id}\n"
        f"# title: {title}\n"
        f"# date: {date_str}\n"
        f"# category: {category}\n"
        f"# model: whisper-{WHISPER_MODEL}\n"
        f"# created: {datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + transcript + "\n")
    return path


async def download_and_transcribe_message(
    client,
    channel_id: int,
    message_id: int,
    *,
    title: str = "",
    date_str: str = "",
    category: str = "",
) -> str:
    """Video indir → transkript → dosyaya kaydet. Mevcut transkript varsa atla."""
    if has_transcript(message_id):
        _log(f"ATLA {message_id} — transkript mevcut")
        return read_transcript(message_id) or ""

    msg = await client.get_messages(channel_id, ids=message_id)
    if not msg or not is_video_message(msg):
        raise RuntimeError(f"Video mesaj bulunamadı: {message_id}")

    text = (msg.text or msg.message or "").strip()
    title = title or title_from_text(text)
    if not date_str and msg.date:
        date_str = msg.date.astimezone(TR_TZ).strftime("%Y-%m-%d %H:%M")

    with tempfile.TemporaryDirectory(prefix=f"haluk_vid_{message_id}_") as tmp:
        video_path = await client.download_media(msg, file=os.path.join(tmp, "video"))
        if not video_path or not os.path.isfile(video_path):
            raise RuntimeError(f"İndirme başarısız: {message_id}")

        size_kb = os.path.getsize(video_path) // 1024
        _log(f"İNDİR {message_id} ({size_kb} KB) — {title[:60]}")
        wav_path = os.path.join(tmp, "audio.wav")
        video_to_wav(video_path, wav_path)
        transcript = transcribe_whisper(wav_path)
        # video tmp içinde — otomatik silinir

    path = save_transcript(
        message_id, transcript, title=title, date_str=date_str, category=category,
    )
    _log(f"KAYIT {message_id} → {path} ({len(transcript)} karakter)")
    return transcript


def load_video_list() -> Dict[str, Any]:
    import json
    with open(VIDEO_LIST_JSON, encoding="utf-8") as f:
        return json.load(f)


def sort_videos_by_priority(videos: list) -> list:
    rank = {c: i for i, c in enumerate(TRANSCRIBE_PRIORITY)}

    def key(v):
        cat = v.get("category") or "Diğer"
        return (rank.get(cat, 999), v.get("date_utc") or "")

    return sorted(videos, key=key)
