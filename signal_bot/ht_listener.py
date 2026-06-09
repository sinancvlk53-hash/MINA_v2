# -*- coding: utf-8 -*-
import asyncio
import atexit
import base64
import json
import os
import re
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

import anthropic
from telethon import TelegramClient, events

api_id   = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'
HT_GROUP_ID = -1003062732797

QUEUE_FILE = os.path.join(os.path.dirname(__file__), 'ht_signals_queue.json')
LOCK_FILE  = os.path.join(os.path.dirname(__file__), 'ht_listener.lock')

UPDATE_TRAP    = ['UPDATE', 'RETEST', 'DURUM']
FILTER_COINS   = ['TOTAL', 'OTHERS', 'BRENT', 'XCU', 'USDT']

client = TelegramClient('session_ht', api_id, api_hash)
claude = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

def _acquire_lock():
    if os.path.exists(LOCK_FILE):
        try:
            pid = open(LOCK_FILE).read().strip()
        except Exception:
            pid = '?'
        print(f"ht_listener zaten çalışıyor (PID {pid}). Çıkılıyor.")
        sys.exit(1)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)


# ---------------------------------------------------------------------------
# Filtreler
# ---------------------------------------------------------------------------

def _is_update_trap(text: str) -> bool:
    upper = text.upper()
    return any(kw in upper for kw in UPDATE_TRAP)


def _is_filter_coin(coin: str) -> bool:
    return any(fc in coin.upper() for fc in FILTER_COINS)


# ---------------------------------------------------------------------------
# Metin sinyali parser
# ---------------------------------------------------------------------------

def parse_text_signal(text: str) -> list:
    """'COIN [kelime] Long/Short' formatını yakala. Örn: HYPE Short, XLM Aşağıdan Long"""
    if _is_update_trap(text):
        return []

    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if not lines:
        return []

    first_line = lines[0]
    words = first_line.split()

    # Long/Short ilk 4 kelimede mi?
    side = None
    for w in words[:4]:
        if re.match(r'^(long|short)$', w, re.IGNORECASE):
            side = 'LONG' if w.upper() == 'LONG' else 'SHORT'
            break
    if not side:
        return []

    # Coin ilk kelime: sadece ASCII harf/rakam, 2-12 karakter
    coin_raw = words[0]
    if not re.match(r'^[A-Za-z]{2,12}(USDT)?$', coin_raw):
        return []

    coin = coin_raw.upper()
    if not coin.endswith('USDT'):
        coin += 'USDT'

    if _is_filter_coin(coin):
        return []

    # Risk seviyesi
    risk_match = re.search(r'Risk[^\d]*(\d+)/10', text, re.IGNORECASE)
    risk = f"{risk_match.group(1)}/10" if risk_match else None

    # Scalp / Swing
    trade_type = None
    if re.search(r'\bScalp\b', text, re.IGNORECASE):
        trade_type = 'Scalp'
    elif re.search(r'\bSwing\b', text, re.IGNORECASE):
        trade_type = 'Swing'

    signal = {'coin': coin, 'side': side, 'source': 'HT_TEXT'}
    if risk:
        signal['risk'] = risk
    if trade_type:
        signal['trade_type'] = trade_type

    return [signal]


# ---------------------------------------------------------------------------
# Görsel sinyali — Claude Vision
# ---------------------------------------------------------------------------

VISION_PROMPT = """Bu görüntü Haluk Hoca'nın Telegram kanalından gelen kripto analiz grafiğidir.

GÖREV: TradingView 'Long Position' veya 'Short Position' aracı ara.
- Long Position: üstü YEŞİL, altı KIRMIZI kutu
- Short Position: üstü KIRMIZI, altı YEŞİL kutu

Bu araç yoksa → {"signals": []}

Araç varsa:
- symbol: grafik başlığındaki coin adı (ETHUSDT → ETH, BTCUSDT → BTC)
- direction: "LONG" veya "SHORT"
- entry: aracın giriş çizgisi fiyatı
- tp: aracın hedef fiyatı
- stop: aracın stop fiyatı
- is_scalp: grafik üzerinde "scalp" yazıyorsa true, yoksa false

Sadece geçerli JSON döndür:
{"signals": [{"symbol": "ETH", "direction": "LONG",
"entry": 2890.48, "tp": 2971.72, "stop": 2844.19, "is_scalp": false}]}"""


def _normalize_vision_signal(raw: dict) -> dict | None:
    symbol = str(raw.get('symbol') or raw.get('coin') or '').upper().strip()
    if symbol.endswith('USDT'):
        symbol = symbol[:-4]
    if not symbol:
        return None
    coin = symbol + 'USDT'
    if _is_filter_coin(coin):
        return None

    direction = str(raw.get('direction') or raw.get('side') or '').upper()
    if direction not in ('LONG', 'SHORT'):
        return None

    out = {
        'coin': coin,
        'side': direction,
        'source': 'HT_VISION',
    }
    for key in ('entry', 'tp', 'stop'):
        val = raw.get(key)
        if val is not None:
            out[key] = val
    if 'is_scalp' in raw:
        out['is_scalp'] = bool(raw.get('is_scalp'))
    elif raw.get('trade_type', '').lower() == 'scalp':
        out['is_scalp'] = True

    # Entry, TP ve Stop üçü de yoksa sinyali atla
    if not out.get('entry') or not out.get('tp') or not out.get('stop'):
        return None

    return out


def _vision_sync(img_b64: str, mime: str) -> list:
    """Senkron Claude Vision çağrısı (run_in_executor içinde çalışır)."""
    try:
        resp = claude.messages.create(
            model='claude-opus-4-5',
            max_tokens=512,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {'type': 'base64', 'media_type': mime, 'data': img_b64}
                    },
                    {'type': 'text', 'text': VISION_PROMPT},
                ]
            }]
        )
        raw = resp.content[0].text.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        data = json.loads(raw)

        if isinstance(data, dict):
            if data.get('skip'):
                return []
            items = data.get('signals')
            if items is None:
                items = [data] if data.get('symbol') or data.get('coin') else []
        elif isinstance(data, list):
            items = data
        else:
            return []

        results = []
        for s in items:
            if not isinstance(s, dict) or s.get('skip'):
                continue
            norm = _normalize_vision_signal(s)
            if norm:
                results.append(norm)
        return results

    except Exception as e:
        print(f'[HT VISION] Parse hatası: {e}')
        return []


async def analyze_image(img_bytes: bytes, mime: str = 'image/jpeg') -> list:
    img_b64 = base64.standard_b64encode(img_bytes).decode('utf-8')
    loop    = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _vision_sync, img_b64, mime)


# ---------------------------------------------------------------------------
# Kuyruk yazma
# ---------------------------------------------------------------------------

def write_queue(signals: list, source_info: str):
    try:
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'signals': signals, 'source': source_info}, f, ensure_ascii=False)
        labels = [f"{s.get('coin', s.get('symbol', '?'))} {s.get('side', s.get('direction', '?'))}" for s in signals]
        print(f"[HT KUYRUK] {', '.join(labels)} → {QUEUE_FILE}")
        for sig in signals:
            try:
                from mina_motor_telegram import notify_ht_signal_queued
                notify_ht_signal_queued(sig, source_info=source_info)
            except Exception as exc:
                print(f"[HT KUYRUK] Telegram bildirimi atlandı: {exc}")
    except Exception as e:
        print(f'[HT KUYRUK] Yazma hatası: {e}')


# ---------------------------------------------------------------------------
# Telegram olay yöneticisi
# ---------------------------------------------------------------------------

@client.on(events.NewMessage(chats=HT_GROUP_ID))
async def handler(event):
    msg  = event.message
    text = msg.text or ''
    now  = datetime.now().strftime('%H:%M:%S')

    # --- METİN SİNYALİ ---
    if text:
        signals = parse_text_signal(text)
        if signals:
            print(f'[HT TEXT {now}] {signals[0]["coin"]} {signals[0]["side"]}')
            write_queue(signals, f'HT Metin | {now}')
            return

    # --- GÖRSEL SİNYALİ ---
    has_photo = bool(msg.photo)
    has_img_doc = (
        msg.document and
        msg.document.mime_type and
        'image' in msg.document.mime_type
    )
    if not (has_photo or has_img_doc):
        return

    # Görsel varsa UPDATE tuzağı metinde de kontrol et
    if text and _is_update_trap(text):
        return

    try:
        img_bytes = await client.download_media(msg, bytes)
        mime      = 'image/jpeg'
        if has_img_doc:
            mime = msg.document.mime_type or 'image/jpeg'

        signals = await analyze_image(img_bytes, mime)
        if signals:
            print(f'[HT VISION {now}] {signals[0].get("coin")} {signals[0].get("side")}')
            write_queue(signals, f'HT Görsel | {now}')

    except Exception as e:
        print(f'[HT GORSEL {now}] Hata: {e}')


# ---------------------------------------------------------------------------
# Ana döngü
# ---------------------------------------------------------------------------

async def main():
    _acquire_lock()
    await client.start()
    print(f'HT sinyal dinleyici başladı (PID {os.getpid()}) — metin + görsel izleniyor...')
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
