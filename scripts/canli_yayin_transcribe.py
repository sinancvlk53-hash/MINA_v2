#!/usr/bin/env python3
"""Download + transcribe Haluk live stream from 25min."""
import os
import subprocess
import sys

ROOT = "/root/MINA_v2"
HIST = os.path.join(ROOT, "signal_bot", "history")
MP3 = os.path.join(HIST, "canli_yayin_20260608.mp3")
OUT = os.path.join(HIST, "canli_yayin_25dk.txt")
URL = "https://youtube.com/live/kpnYLBT-H24"
START_SEC = 1500  # 25. dakika
COOKIES = os.environ.get("YOUTUBE_COOKIES", "/root/MINA_v2/signal_bot/history/youtube_cookies.txt")

sys.path.insert(0, ROOT)
os.chdir(HIST)

print("=== ADIM 1: yt-dlp indirme ===")
print("URL:", URL)
print("cikti:", MP3)
cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", "canli_yayin_20260608.mp3", URL]
if os.path.isfile(COOKIES):
    cmd[1:1] = ["--cookies", COOKIES]
    print("cookies:", COOKIES)
else:
    print("cookies: (yok — uye icerigi icin gerekli olabilir)")
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout)
print(r.stderr)
if r.returncode != 0:
    print("INDIRME BASARISIZ exit=", r.returncode)
    sys.exit(r.returncode)

if not os.path.isfile(MP3):
    # yt-dlp may add extension
    for f in os.listdir(HIST):
        if f.startswith("canli_yayin_20260608"):
            MP3 = os.path.join(HIST, f)
            break

print("dosya:", MP3, "boyut:", os.path.getsize(MP3) if os.path.isfile(MP3) else "YOK")

print("\n=== ADIM 2: Whisper transkript (25. dk+) ===")
import whisper

model = whisper.load_model("base")
result = model.transcribe(MP3, language="tr", verbose=False)
segments = [s for s in result["segments"] if s["start"] >= START_SEC]
text = " ".join(s["text"].strip() for s in segments)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print("segment sayisi (25dk+):", len(segments))
print("karakter:", len(text))
print("kayit:", OUT)
print("--- ilk 500 karakter ---")
print(text[:500])
print("\nTamamlandi.")
