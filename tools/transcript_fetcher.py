# -*- coding: utf-8 -*-
"""
YouTube video transcript -> Claude API analizi -> Telegram
Kullanim: python transcript_fetcher.py <youtube_url>
"""
import sys, os, re, requests
from datetime import datetime

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv; load_dotenv(os.path.join(_ROOT, '.env'))

from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
import anthropic

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ANTHROPIC_KEY    = os.getenv('ANTHROPIC_API_KEY')
OUT_DIR          = os.path.join(_ROOT, 'signal_bot', 'history')


def extract_video_id(url):
    patterns = [
        r'(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"Video ID bulunamadi: {url}")


def fetch_transcript(video_id):
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=['tr', 'en'])
        lang = fetched.language_code
    except NoTranscriptFound:
        transcript_list = api.list(video_id)
        t = next(iter(transcript_list))
        fetched = t.fetch()
        lang = t.language_code
    text = ' '.join(seg.text for seg in fetched)
    return text, lang


def save_transcript(video_id, text, lang):
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    fname = os.path.join(OUT_DIR, f'transcript_{video_id}_{ts}.txt')
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Transcript kaydedildi: {fname} ({lang}, {len(text)} karakter)")
    return fname


def analyze_with_claude(text):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    max_chars = 180_000
    if len(text) > max_chars:
        text = text[:max_chars]
        print(f"Transcript kisaltildi: {max_chars} karakter")

    prompt = (
        "Bu bir trading eğitimi videosunun transkriptidir. "
        "Videoda anlatilan strateji kurallarini madde madde cikar. "
        "Giriş koşulları, çıkış koşulları, stop loss, take profit, "
        "kaldıraç, risk yönetimi, coin/enstrüman seçimi, zaman dilimi gibi "
        "somut kuralları listele. Belirsiz veya genel ifadeleri atla, "
        "sadece spesifik, uygulanabilir kuralları yaz.\n\n"
        f"Transkript:\n{text}"
    )

    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text


def send_telegram(text, video_url):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bilgileri eksik, atlanıyor.")
        return

    max_len = 4000
    header = f"*YouTube Strateji Analizi*\n{video_url}\n\n"
    body = text

    chunks = []
    remaining = header + body
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        split_at = remaining.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip('\n')

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i, chunk in enumerate(chunks):
        resp = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': chunk,
            'parse_mode': 'Markdown',
        }, timeout=15)
        if resp.ok:
            print(f"Telegram gonderildi ({i+1}/{len(chunks)})")
        else:
            print(f"Telegram hata ({i+1}): {resp.text}")


def main():
    if len(sys.argv) < 2:
        print("Kullanim: python transcript_fetcher.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"URL: {url}")

    video_id = extract_video_id(url)
    print(f"Video ID: {video_id}")

    print("Transcript cekiliyor...")
    text, lang = fetch_transcript(video_id)
    print(f"Dil: {lang}, Uzunluk: {len(text)} karakter")

    save_transcript(video_id, text, lang)

    print("Claude API ile analiz ediliyor...")
    analysis = analyze_with_claude(text)
    print("\n--- ANALIZ ---")
    print(analysis.encode('ascii', errors='replace').decode('ascii'))
    print("--------------\n")

    print("Telegram'a gonderiliyor...")
    send_telegram(analysis, url)

    print("Tamamlandi.")


if __name__ == '__main__':
    main()
