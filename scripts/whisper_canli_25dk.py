#!/usr/bin/env python3
import whisper

MP3 = "/root/MINA_v2/signal_bot/history/canli_yayin.mp3"
OUT = "/root/MINA_v2/signal_bot/history/canli_yayin_25dk.txt"
START_SEC = 1500

print("Model yukleniyor: base")
model = whisper.load_model("base")
print("Transkript basliyor:", MP3)
result = model.transcribe(MP3, language="tr", verbose=False)
segments = [s for s in result["segments"] if s["start"] >= START_SEC]
text = "\n".join(
    f"[{int(s['start'] // 60)}:{int(s['start'] % 60):02d}] {s['text']}"
    for s in segments
)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print("Tamamlandi:", len(segments), "segment")
print("Kayit:", OUT)
print("Karakter:", len(text))
if text:
    print("--- ilk 500 karakter ---")
    print(text[:500])
