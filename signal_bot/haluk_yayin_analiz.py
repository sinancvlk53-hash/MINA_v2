#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Haluk Hoca canlı yayın — yt-dlp indir, Whisper, Claude JSON, DB, Telegram."""

from __future__ import annotations



import json

import os

import re

import subprocess

import sys

import threading

import time

from datetime import datetime, timezone, timedelta

from typing import Any, Dict, List, Optional, Set, Tuple



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

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

CLAUDE_MODEL = os.getenv("HALUK_YAYIN_ANALIZ_MODEL", "claude-sonnet-4-6")



INITIAL_WAIT_SEC = int(os.getenv("YAYIN_ANALIZ_INITIAL_WAIT", "300"))

LIVE_CHECK_SEC = int(os.getenv("YAYIN_LIVE_CHECK_SEC", "300"))



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



CLAUDE_JSON_PROMPT = """

Aşağıdaki transkript Haluk Hoca'nın kripto analiz yayınından alınmıştır.

Sadece ve sadece aşağıdaki JSON formatında çıktı ver, başka hiçbir şey yazma:



{

  "genel_piyasa_yonu": "BULLISH/BEARISH/NEUTRAL",

  "onemli_haberler": ["haber1", "haber2"],

  "incelenen_coinler": [

    {

      "coin": "BTC",

      "strateji": "Long/Short/Wait",

      "destekler": [68200, 67500],

      "direncler": [69500, 70200],

      "kritik_seviye": 68500,

      "formasyon": "Order Block / FVG / vb"

    }

  ]

}



Transkript:

{transkript}

"""



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





def wait_for_live_end(youtube_url: str) -> None:

    """Yayın canlıysa 5 dk aralıkla kontrol et; bitince devam et."""

    _log(f"Yayın bitene kadar bekleniyor: {youtube_url}")

    while True:

        if not is_stream_live(youtube_url):

            _log(f"Yayın bitti: {youtube_url}")

            return

        _log(f"Hâlâ canlı — {LIVE_CHECK_SEC}s sonra tekrar kontrol")

        time.sleep(LIVE_CHECK_SEC)





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





def _transcribe(mp3_path: str) -> Tuple[str, int]:

    model = _get_whisper_model()

    _log(f"Transkript: {mp3_path}")

    result = model.transcribe(mp3_path, language="tr", verbose=False, fp16=False)

    text = (result.get("text") or "").strip()

    if not text:

        raise RuntimeError("Whisper boş transkript döndü")

    segments = result.get("segments") or []

    sure = int(segments[-1]["end"]) if segments else 0

    return text, sure





def _transcript_fallback_message(transkript: str) -> str:

    snippet = transkript[:2000]

    suffix = "..." if len(transkript) > 2000 else ""

    return (

        "📺 Haluk Hoca Yayın Transkripti\n"

        "(Claude analizi geçici olarak devre dışı)\n\n"

        f"{snippet}{suffix}"

    )





def _parse_claude_json(raw: str) -> Dict[str, Any]:

    text = (raw or "").strip()

    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)

    if m:

        text = m.group(1).strip()

    start = text.find("{")

    end = text.rfind("}")

    if start >= 0 and end > start:

        text = text[start:end + 1]

    data = json.loads(text)

    if not isinstance(data, dict):

        raise ValueError("Claude JSON kök obje değil")

    return data





def _analyze_claude_json(transkript: str) -> Tuple[Dict[str, Any], str]:

    prompt = CLAUDE_JSON_PROMPT.format(transkript=transkript[:12000])

    import anthropic

    client = anthropic.Anthropic()

    resp = client.messages.create(

        model=CLAUDE_MODEL,

        max_tokens=4000,

        messages=[{"role": "user", "content": prompt}],

    )

    raw = resp.content[0].text

    return _parse_claude_json(raw), raw





def _format_telegram_summary(data: Dict[str, Any]) -> str:

    lines = ["📺 Haluk Hoca Yayın Özeti (Final)\n"]

    yon = data.get("genel_piyasa_yonu")

    if yon:

        lines.append(f"🌐 Genel piyasa yönü: {yon}\n")

    haberler = data.get("onemli_haberler") or []

    if haberler:

        lines.append("📰 Önemli haberler:")

        for h in haberler:

            lines.append(f"  • {h}")

        lines.append("")

    coins = data.get("incelenen_coinler") or []

    if coins:

        lines.append("🪙 İncelenen coinler:")

        for c in coins:

            if not isinstance(c, dict):

                continue

            coin = c.get("coin", "?")

            strat = c.get("strateji", "")

            kritik = c.get("kritik_seviye", "")

            form = c.get("formasyon", "")

            lines.append(f"  • {coin} — {strat} | kritik: {kritik} | {form}")

    return "\n".join(lines)





def _format_coin_telegram(coin: Dict[str, Any]) -> str:

    destek = coin.get("destekler") or []

    direnc = coin.get("direncler") or []

    return (

        "🚨 Haluk Hoca Coin Analizi\n"

        f"{coin.get('coin', '?')} — {coin.get('strateji', '')}\n"

        f"Destekler: {destek}\n"

        f"Dirençler: {direnc}\n"

        f"Kritik: {coin.get('kritik_seviye', '')}\n"

        f"Formasyon: {coin.get('formasyon', '')}"

    )





def _send_coin_telegrams_from_json(data: Dict[str, Any]) -> int:

    sent = 0

    for item in data.get("incelenen_coinler") or []:

        if not isinstance(item, dict) or not item.get("coin"):

            continue

        if _send_telegram(_format_coin_telegram(item)):

            sent += 1

            _log(f"Coin analizi gönderildi: {item.get('coin')}")

    return sent





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





def _save_analysis_to_db(

    *,

    message_id: Optional[int],

    youtube_url: str,

    data: Dict[str, Any],

    ham_json: str,

    transkript_path: str,

    sure_saniye: int,

) -> List[int]:

    if not message_id:

        _log("DB kaydı atlandı (message_id yok)")

        return []

    from signal_bot.haluk_yayin_db import save_yayin_analysis

    from signal_bot.haluk_coin_price_tracker import capture_baz_prices_for_rows



    vid = _video_id(youtube_url)

    video_date = datetime.now(TR_TZ).strftime("%Y-%m-%d")

    row_ids = save_yayin_analysis(

        message_id=message_id,

        video_id=vid,

        video_url=youtube_url,

        video_date=video_date,

        data=data,

        ham_json=ham_json,

        transkript_path=transkript_path,

        whisper_model=WHISPER_MODEL,

        sure_saniye=sure_saniye,

    )

    if row_ids:

        n = capture_baz_prices_for_rows(row_ids)

        _log(f"DB kaydedildi: msg={message_id} coins={len(row_ids)} baz_fiyat={n}")

    return row_ids





def _run_final_analysis(url: str, message_id: Optional[int]) -> None:

    mp3 = _download_mp3(url)

    transkript, sure_saniye = _transcribe(mp3)

    transkript_path = _save_transcript(url, transkript, message_id)



    try:

        data, ham_json = _analyze_claude_json(transkript)

        _send_telegram(_format_telegram_summary(data))

        n = _send_coin_telegrams_from_json(data)

        if n:

            _log(f"Toplam {n} coin analizi Telegram'a gönderildi")

        _save_analysis_to_db(

            message_id=message_id,

            youtube_url=url,

            data=data,

            ham_json=ham_json,

            transkript_path=transkript_path,

            sure_saniye=sure_saniye,

        )

    except Exception as exc:

        _log(f"Claude/DB hatası (transkript fallback): {exc}")

        _send_telegram(_transcript_fallback_message(transkript))





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

            _log(f"{INITIAL_WAIT_SEC}s bekleniyor: {url}")

            time.sleep(INITIAL_WAIT_SEC)

            _send_telegram(f"⏳ Yayın analiz ediliyor (bitene kadar bekleniyor)...\n{url}")

            wait_for_live_end(url)



        _run_final_analysis(url, message_id)

        _mark_processed(message_id, url)

    finally:

        with _active_lock:

            _active_urls.discard(url)





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

        analiz_et(url, skip_wait=True, watch_mode=False)

    else:

        analiz_et(url)





if __name__ == "__main__":

    main()

