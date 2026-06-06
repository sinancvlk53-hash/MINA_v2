# -*- coding: utf-8 -*-
"""
MINA v2 — Birleşik Telegram Sinyal Dinleyici (Katman 1)

Merter ve Haluk Hoca ayrı Telethon oturumları ile dinlenir:
  - session.session     → Merter (TELEGRAM_MERTER_SESSION)
  - session_ht.session  → Haluk  (TELEGRAM_HALUK_SESSION)

Her yeni mesaj → signal_parser → raw_signal_queue.json
"""

from __future__ import annotations

import asyncio
import atexit
import os
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from telethon import TelegramClient, events

from signal_bot.signal_parser import (
    enqueue_records,
    parse_haluk_telegram,
    parse_merter,
    parse_pdf_and_enqueue,
)


def _env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


API_ID = _env_int("TELEGRAM_API_ID", 0)
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
MERTER_CHANNEL_ID = _env_int("TELEGRAM_MERTER_CHANNEL_ID", 0)
HALUK_CHANNEL_ID = _env_int("TELEGRAM_HALUK_CHANNEL_ID", 0)

# Oturum dosyaları proje kökünde (Telethon .session uzantısını kendisi ekler)
MERTER_SESSION = os.path.join(
    _ROOT, os.getenv("TELEGRAM_MERTER_SESSION", "session").strip()
)
HALUK_SESSION = os.path.join(
    _ROOT, os.getenv("TELEGRAM_HALUK_SESSION", "session_ht").strip()
)

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = os.path.join(SIGNAL_BOT_DIR, "listener.lock")
LOG_FILE = os.path.join(SIGNAL_BOT_DIR, "signals_log.txt")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_lock() -> None:
    if os.path.exists(LOCK_FILE):
        stale = False
        try:
            pid = int(open(LOCK_FILE, encoding="utf-8").read().strip())
        except (OSError, ValueError):
            stale = True
        else:
            if not _pid_alive(pid):
                stale = True
        if stale:
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        else:
            print(f"listener zaten çalışıyor (PID {pid}). Çıkılıyor.")
            sys.exit(1)
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)


def _log(line: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {line}"
    print(msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _validate_config() -> None:
    if not API_ID or not API_HASH:
        print("HATA: TELEGRAM_API_ID ve TELEGRAM_API_HASH .env içinde tanımlı olmalı.")
        sys.exit(1)
    if not MERTER_CHANNEL_ID and not HALUK_CHANNEL_ID:
        print("HATA: En az bir kanal ID gerekli (MERTER veya HALUK).")
        sys.exit(1)


def _dispatch_merter(text: str, msg_id: int) -> None:
    preview = text[:200].replace("\n", " ")
    _log(f"[MERTER] İLK MESAJ / YENİ | id={msg_id} | metin: {preview}")

    try:
        from signal_bot.merter_dca_manager import get_merter_dca_manager
        if get_merter_dca_manager().handle_message(text):
            _log("[MERTER] → merter_dca_manager işledi (EI/RSI 1x DCA)")
            return
    except Exception as e:
        _log(f"[MERTER] DCA hatası (devam): {e}")

    records = parse_merter(text)
    if records:
        enqueue_records(records)
        _log(f"[MERTER] → {len(records)} kayıt kuyruğa yazıldı (K2/K3: queue_watcher)")
    else:
        _log(f"[MERTER] parse sonucu boş")


def _dispatch_haluk_text(text: str, msg_id: int) -> None:
    preview = text[:200].replace("\n", " ")
    _log(f"[HALUK] İLK MESAJ / YENİ | id={msg_id} | metin: {preview}")
    try:
        from signal_bot.haluk_message_store import archive_haluk_message_async
        archive_haluk_message_async(text, message_id=msg_id)
    except Exception as e:
        _log(f"[HALUK] arşiv hatası: {e}")
    records, pause = parse_haluk_telegram(text)
    if records:
        enqueue_records(records)
        _log(f"[HALUK] → {len(records)} kayıt (pause={pause})")
    else:
        _log(f"[HALUK] parse sonucu boş")


async def _dispatch_haluk_pdf(event: events.NewMessage.Event, msg_id: int) -> None:
    pdf_dir = os.path.join(SIGNAL_BOT_DIR, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(pdf_dir, f"tg_{ts}_{msg_id}.pdf")
    await event.message.download_media(file=filepath)
    _log(f"[HALUK PDF] indirildi: {filepath}")
    try:
        from signal_bot.haluk_message_store import archive_haluk_message_async
        archive_haluk_message_async(
            f"[PDF] {os.path.basename(filepath)}",
            message_id=msg_id,
        )
    except Exception as e:
        _log(f"[HALUK PDF] arşiv hatası: {e}")
    records = parse_pdf_and_enqueue(filepath)
    _log(f"[HALUK PDF] → {len(records)} kayıt")


def _make_merter_client() -> TelegramClient:
    return TelegramClient(MERTER_SESSION, API_ID, API_HASH)


def _make_haluk_client() -> TelegramClient:
    return TelegramClient(HALUK_SESSION, API_ID, API_HASH)


async def _run_merter_listener() -> None:
    client = _make_merter_client()

    @client.on(events.NewMessage(chats=MERTER_CHANNEL_ID))
    async def handler(event: events.NewMessage.Event) -> None:
        text = (event.message.text or event.message.message or "").strip()
        if not text:
            return
        _dispatch_merter(text, event.message.id)

    await client.start()
    _log(f"[MERTER] dinleniyor ch={MERTER_CHANNEL_ID} session={MERTER_SESSION}.session")
    await client.run_until_disconnected()


async def _run_haluk_listener() -> None:
    client = _make_haluk_client()

    @client.on(events.NewMessage(chats=HALUK_CHANNEL_ID))
    async def handler(event: events.NewMessage.Event) -> None:
        doc = event.message.document
        if doc and getattr(doc, "mime_type", None) == "application/pdf":
            await _dispatch_haluk_pdf(event, event.message.id)
            return
        text = (event.message.text or event.message.message or "").strip()
        if not text:
            return
        _dispatch_haluk_text(text, event.message.id)

    await client.start()
    _log(f"[HALUK] dinleniyor ch={HALUK_CHANNEL_ID} session={HALUK_SESSION}.session")
    await client.run_until_disconnected()


async def main() -> None:
    _acquire_lock()
    _validate_config()

    _log("=" * 60)
    _log("MINA listener — ayrı oturumlar (Merter + Haluk)")
    _log(f"  API_ID      : {API_ID}")
    _log(f"  Merter      : ch={MERTER_CHANNEL_ID} session={MERTER_SESSION}.session")
    _log(f"  Haluk       : ch={HALUK_CHANNEL_ID} session={HALUK_SESSION}.session")
    _log("=" * 60)

    tasks = []
    if MERTER_CHANNEL_ID:
        tasks.append(asyncio.create_task(_run_merter_listener()))
    if HALUK_CHANNEL_ID:
        tasks.append(asyncio.create_task(_run_haluk_listener()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
