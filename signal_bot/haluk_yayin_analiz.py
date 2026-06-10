#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Haluk Hoca canlı yayın — yt-dlp indir, Whisper, Claude özet, Telegram."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

_ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

HIST = os.path.join(_ROOT, "signal_bot", "history")
TRANSCRIPT_DIR = os.path.join(HIST, "transcripts")
COOKIES = os.path.join(HIST, "youtube_cookies.txt")
MP3_PATH = os.path.join(HIST, "son_yayin.mp3")
STATE_PATH = os.path.join(HIST, "yayin_analiz_state.json")
LOG_PATH = os.path.join(_ROOT, "signal_bot", "yayin_analiz.log")

YTDLP = os.getenv("YTDLP_BIN", "/usr/local/bin/yt-dlp")
DENO = os.getenv("DENO_BIN", "/root/.deno/bin/deno")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
CLAUDE_MODEL = os.getenv("HALUK_YAYIN_ANALIZ_MODEL", "claude-sonnet-4-6")

INITIAL_WAIT_SEC = int(os.getenv("YAYIN_ANALIZ_INITIAL_WAIT", "300"))
POLL_INTERVAL_SEC = int(os.getenv("YAYIN_ANALIZ_POLL_SEC", "1800"))

TR_TZ = timezone(timedelta(hours=3))

YOUTUBE_YAYIN_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/live/[\w-]+(?:\?[^\s\])>]*)?"
    r"|youtu\.be/[\w-]+(?:\?[^\s\])>]*)?)",
    re.I,
)

CRYPTO_TITLE_KEYWORDS = (
    "bitcoin", "btc", "eth", "kripto", "crypto",
    "altcoin", "analiz", "piyasa", "borsa",
    "long", "short", "coin", "token", "chart",
    "yayın özeti", "teknik",
)

SKIP_TITLE_KEYWORDS = (
    "gündem", "sohbet", "röportaj", "podcast",
    "vlog", "daily", "hayat", "yemek", "gezi",
    "müzik", "film", "spor",
)

_whisper_model = None
_whisper_lock = threading.Lock()
_active_urls: Set[str] = set()
_active_lock = threading.Lock()


def _log(msg: str) -> None:
    line = f"[{datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def extract_youtube_yayin_urls(text: str) -> List[str]:
    if not text:
        return []
    found: List[str] = []
    seen: Set[str] = set()
    for m in YOUTUBE_YAYIN_RE.finditer(text):
        url = m.group(0).rstrip(".,;)")
        if url not in seen:
            seen.add(url)
            found.append(url)
    return found


def _video_id(url: str) -> str:
    m = re.search(r"youtu\.be/([\w-]+)", url)
    if m:
        return m.group(1)[:11]
    m = re.search(r"live/([\w-]+)", url)
    if m:
        return m.group(1)[:11]
    m = re.search(r"[?&]v=([\w-]+)", url)
    if m:
        return m.group(1)[:11]
    return url[-11:]


def _read_state() -> Dict[str, Any]:
    if not os.path.isfile(STATE_PATH):
        return {"processed_messages": [], "processed_urls": []}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"processed_messages": [], "processed_urls": []}


def _write_state(state: Dict[str, Any]) -> None:
    os.makedirs(HIST, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _already_processed(message_id: Optional[int], url: str) -> bool:
    state = _read_state()
    if message_id and message_id in state.get("processed_messages", []):
        return True
    if url in state.get("processed_urls", []):
        return True
    return False


def _mark_processed(message_id: Optional[int], url: str) -> None:
    state = _read_state()
    msgs = state.setdefault("processed_messages", [])
    urls = state.setdefault("processed_urls", [])
    if message_id and message_id not in msgs:
        msgs.append(message_id)
    if url not in urls:
        urls.append(url)
    _write_state(state)


def _send_telegram(text: str) -> bool:
    try:
        from tools.telegram_bot import send_notification
        return bool(send_notification(text))
    except Exception as exc:
        _log(f"Telegram hatası: {exc}")
        return False


def _yt_dlp_base_cmd() -> List[str]:
    cmd = [YTDLP]
    if os.path.isfile(COOKIES):
        cmd.extend(["--cookies", COOKIES])
    if os.path.isfile(DENO):
        cmd.extend(["--js-runtimes", f"deno:{DENO}", "--remote-components", "ejs:github"])
    return cmd


def _fetch_video_title(youtube_url: str) -> Optional[str]:
    cmd = _yt_dlp_base_cmd() + ["--print", "%(title)s", "--skip-download", youtube_url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        title = (r.stdout or "").strip()
        if r.returncode == 0 and title:
            return title
        if r.stderr:
            _log(f"Başlık alınamadı stderr: {r.stderr[-500:]}")
    except Exception as exc:
        _log(f"Başlık alınamadı: {exc}")
    return None


def _is_crypto_related_title(title: str) -> bool:
    t = title.casefold()
    for kw in SKIP_TITLE_KEYWORDS:
        if kw.casefold() in t:
            return False
    for kw in CRYPTO_TITLE_KEYWORDS:
        if kw.casefold() in t:
            return True
    return False


def _check_title_or_skip(url: str, message_id: Optional[int]) -> bool:
    """True = kripto ile ilgili, işleme devam. False = atla."""
    title = _fetch_video_title(url)
    if not title:
        _log(f"Başlık okunamadı, güvenli atlama: {url}")
        _mark_processed(message_id, url)
        return False
    if not _is_crypto_related_title(title):
        _log(f"Kripto dışı video atlandı: {title}")
        _mark_processed(message_id, url)
        return False
    _log(f"Kripto yayın onaylandı: {title}")
    return True


def is_stream_live(youtube_url: str) -> bool:
    cmd = _yt_dlp_base_cmd() + ["--print", "%(is_live)s", youtube_url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        val = (r.stdout or "").strip().lower()
        if val in ("true", "1", "yes"):
            return True
        if val in ("false", "0", "no"):
            return False
    except Exception as exc:
        _log(f"is_live kontrol hatası: {exc}")
    return False


def _download_mp3(youtube_url: str) -> str:
    os.makedirs(HIST, exist_ok=True)
    cmd = _yt_dlp_base_cmd() + [
        "-x", "--audio-format", "mp3",
        "-o", MP3_PATH,
        youtube_url,
    ]
    _log(f"İndiriliyor: {youtube_url}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        _log(f"yt-dlp stderr: {r.stderr[-2000:]}")
        if os.path.isfile(MP3_PATH) and os.path.getsize(MP3_PATH) > 10_000:
            _log(f"İndirme başarısız — mevcut MP3 kullanılıyor: {MP3_PATH}")
            return MP3_PATH
        _send_telegram(f"❌ Yayın indirilemedi:\n{youtube_url}\n\nCookie güncelleme gerekebilir.")
        raise RuntimeError(f"yt-dlp exit {r.returncode}")

    if os.path.isfile(MP3_PATH):
        return MP3_PATH
    for name in os.listdir(HIST):
        if name.startswith("son_yayin.") and name.endswith(".mp3"):
            path = os.path.join(HIST, name)
            if path != MP3_PATH:
                os.replace(path, MP3_PATH)
            return MP3_PATH
    raise RuntimeError("MP3 dosyası oluşmadı")


def _get_whisper_model():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            import whisper
            _log(f"Whisper model yükleniyor: {WHISPER_MODEL}")
            _whisper_model = whisper.load_model(WHISPER_MODEL)
        return _whisper_model


def _transcribe(mp3_path: str) -> str:
    model = _get_whisper_model()
    _log(f"Transkript: {mp3_path}")
    result = model.transcribe(mp3_path, language="tr", verbose=False, fp16=False)
    text = (result.get("text") or "").strip()
    if not text:
        raise RuntimeError("Whisper boş transkript döndü")
    return text


def _transcript_fallback_message(transkript: str) -> str:
    snippet = transkript[:2000]
    suffix = "..." if len(transkript) > 2000 else ""
    return (
        "📺 Haluk Hoca Yayın Transkripti\n"
        "(Claude analizi geçici olarak devre dışı)\n\n"
        f"{snippet}{suffix}"
    )


def _claude_analiz_prompt(transkript: str, *, final: bool) -> str:
    kind_note = ""
    if not final:
        kind_note = "\n(Bu bir ARA özet — yayın devam ediyor; şu ana kadarki transkripti analiz et.)\n"
    return f"""Sen bir kripto analiz asistanısın.
Aşağıdaki transkripti analiz et.{kind_note}

BÖLÜM 1 — GENEL PİYASA GÖRÜŞÜ:
Hoca piyasa hakkında ne düşünüyor?
BTC, ETH, TOTAL için ne dedi?
Yön yukarı mı aşağı mı?

BÖLÜM 2 — COİN SİNYALLERİ:
Hoca hangi coinleri AL dedi?
Hangi coinleri SAT/SHORT dedi?
Her coin için şu şablona uy (coin yoksa "Bu bölümde coin sinyali yok" yaz):
COIN: [sembol]
YÖN: LONG veya SHORT
GİRİŞ: [seviye veya bilinmiyor]
HEDEF: [seviye veya bilinmiyor]
STOP: [seviye veya yok]
NOT: [hoca ne dedi]
---

BÖLÜM 3 — KRİTİK SEVİYELER:
Önemli destek/direnç seviyeleri neler?
Kırılırsa ne olur?

BÖLÜM 4 — UYARILAR:
Hoca özellikle neye dikkat etmemizi söyledi?
Risk faktörleri neler?

BÖLÜM 5 — ÖZET:
2-3 cümleyle genel özet.

Transkript:
{transkript[:12000]}"""


_COIN_SIGNAL_BLOCK_RE = re.compile(
    r"COIN:\s*(?P<coin>[^\n]+)\s*\n"
    r"YÖN:\s*(?P<direction>[^\n]+)\s*\n"
    r"GİRİŞ:\s*(?P<entry>[^\n]+)\s*\n"
    r"HEDEF:\s*(?P<target>[^\n]+)\s*\n"
    r"STOP:\s*(?P<stop>[^\n]+)\s*\n"
    r"NOT:\s*(?P<note>[^\n]+)",
    re.I,
)


def _extract_bolum2(ozet: str) -> str:
    m = re.search(r"BÖLÜM\s*2[^\n]*\n(.*?)BÖLÜM\s*3", ozet, re.I | re.S)
    if m:
        return m.group(1)
    m = re.search(r"BÖLÜM\s*2[^\n]*\n(.*)", ozet, re.I | re.S)
    return m.group(1) if m else ""


def _parse_coin_signals(ozet: str) -> List[Dict[str, str]]:
    bolum2 = _extract_bolum2(ozet)
    if not bolum2 or re.search(r"coin sinyali yok", bolum2, re.I):
        return []
    signals: List[Dict[str, str]] = []
    for m in _COIN_SIGNAL_BLOCK_RE.finditer(bolum2):
        coin = m.group("coin").strip()
        if not coin or coin.lower() in ("yok", "none", "-"):
            continue
        signals.append({
            "coin": coin,
            "direction": m.group("direction").strip(),
            "entry": m.group("entry").strip(),
            "target": m.group("target").strip(),
            "stop": m.group("stop").strip(),
            "note": m.group("note").strip(),
        })
    return signals


def _format_coin_signal_message(sig: Dict[str, str]) -> str:
    return (
        "🚨 Haluk Hoca Coin Sinyali\n"
        f"{sig['coin']} {sig['direction']}\n"
        f"Giriş: {sig['entry']}\n"
        f"Hedef: {sig['target']}\n"
        f"Stop: {sig['stop']}\n"
        f"Not: {sig['note']}"
    )


def _send_coin_signal_telegrams(ozet: str) -> int:
    signals = _parse_coin_signals(ozet)
    sent = 0
    for sig in signals:
        if _send_telegram(_format_coin_signal_message(sig)):
            sent += 1
            _log(f"Coin sinyali gönderildi: {sig['coin']} {sig['direction']}")
    return sent


def _analyze_claude(transkript: str, *, final: bool = False) -> str:
    prompt = _claude_analiz_prompt(transkript, final=final)

    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _save_transcript(youtube_url: str, transkript: str, message_id: Optional[int] = None) -> str:
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    vid = _video_id(youtube_url)
    ts = datetime.now(TR_TZ).strftime("%Y%m%d_%H%M")
    name = f"yayin_{vid}"
    if message_id:
        name = f"{message_id}_{name}"
    path = os.path.join(TRANSCRIPT_DIR, f"{name}_{ts}.txt")
    header = (
        f"# url: {youtube_url}\n"
        f"# message_id: {message_id or ''}\n"
        f"# created: {datetime.now(TR_TZ).isoformat()}\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + transkript)
    _log(f"Transkript kaydedildi: {path}")
    return path


def analiz_et(
    youtube_url: str,
    *,
    message_id: Optional[int] = None,
    skip_wait: bool = False,
    watch_mode: bool = True,
) -> None:
    """Tek URL için tam analiz döngüsü."""
    url = youtube_url.strip()
    if _already_processed(message_id, url) and not skip_wait:
        _log(f"ATLA (zaten işlendi): msg={message_id} url={url}")
        return

    with _active_lock:
        if url in _active_urls:
            _log(f"ATLA (aktif işlem var): {url}")
            return
        _active_urls.add(url)

    try:
        if not _check_title_or_skip(url, message_id):
            return

        if watch_mode and not skip_wait:
            _run_watch_loop(url, message_id)
        else:
            _run_single_pass(url, message_id, final=True)
            _mark_processed(message_id, url)
    finally:
        with _active_lock:
            _active_urls.discard(url)


def _run_single_pass(
    url: str,
    message_id: Optional[int],
    *,
    final: bool,
    interim_no: int = 0,
) -> tuple[str, str]:
    mp3 = _download_mp3(url)
    transkript = _transcribe(mp3)
    if final:
        _save_transcript(url, transkript, message_id)
    try:
        ozet = _analyze_claude(transkript, final=final)
        if final:
            label = "📺 Haluk Hoca Yayın Özeti (Final)\n\n"
        else:
            label = f"📺 Haluk Yayın — Ara Özet #{interim_no}\n\n"
        _send_telegram(label + ozet)
        if final:
            n = _send_coin_signal_telegrams(ozet)
            if n:
                _log(f"Toplam {n} coin sinyali Telegram'a gönderildi")
    except Exception as exc:
        _log(f"Claude API hatası (transkript fallback): {exc}")
        _send_telegram(_transcript_fallback_message(transkript))
        ozet = ""
    return transkript, ozet


def _run_watch_loop(url: str, message_id: Optional[int]) -> None:
    _log(f"5 dk bekleniyor: {url}")
    time.sleep(INITIAL_WAIT_SEC)

    _send_telegram(f"⏳ Yayın analiz ediliyor...\n{url}")

    last_len = 0
    interim_no = 0
    live_seen = False

    while True:
        try:
            live = is_stream_live(url)
            if live:
                live_seen = True

            transkript, _ = _run_single_pass(
                url, message_id,
                final=not live,
                interim_no=interim_no + 1 if live else 0,
            )
            tlen = len(transkript)

            if not live:
                _log(f"Yayın bitti — final özet gönderildi: {url}")
                _mark_processed(message_id, url)
                break

            if tlen > last_len + 100:
                last_len = tlen
                interim_no += 1

            _log(f"Canlı devam — {POLL_INTERVAL_SEC}s sonra tekrar: {url}")
            time.sleep(POLL_INTERVAL_SEC)

        except Exception as exc:
            _log(f"Döngü hatası: {exc}")
            if live_seen and not is_stream_live(url):
                try:
                    _run_single_pass(url, message_id, final=True)
                    _mark_processed(message_id, url)
                except Exception as exc2:
                    _log(f"Final deneme hatası: {exc2}")
                break
            time.sleep(300)


def extract_youtube_urls(text: str) -> List[str]:
    """listener.py uyumluluğu."""
    return extract_youtube_yayin_urls(text)


def schedule_yayin_analiz(youtube_url: str, message_id: Optional[int] = None) -> None:
    """listener.py — arka planda analiz başlat."""
    if _already_processed(message_id, youtube_url):
        _log(f"schedule ATLA: msg={message_id} url={youtube_url}")
        return

    if not _check_title_or_skip(youtube_url, message_id):
        return

    _send_telegram(
        f"⏳ Haluk yayın linki alındı — 5 dk sonra analiz başlayacak.\n{youtube_url}"
    )

    t = threading.Thread(
        target=analiz_et,
        args=(youtube_url,),
        kwargs={"message_id": message_id, "watch_mode": True},
        daemon=True,
        name=f"yayin-analiz-{message_id or _video_id(youtube_url)}",
    )
    t.start()
    _log(f"schedule başlatıldı: msg={message_id} url={youtube_url}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Kullanım: haluk_yayin_analiz.py [--test] <youtube_url>")
        sys.exit(1)

    test_mode = False
    if args[0] == "--test":
        test_mode = True
        args = args[1:]

    if not args:
        print("URL gerekli")
        sys.exit(1)

    url = args[0]
    if test_mode:
        os.environ["YAYIN_ANALIZ_INITIAL_WAIT"] = "0"
        os.environ["YAYIN_ANALIZ_POLL_SEC"] = "0"
        analiz_et(url, skip_wait=True, watch_mode=False)
    else:
        analiz_et(url)


if __name__ == "__main__":
    main()
