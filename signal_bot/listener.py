import asyncio
import re
import sys
from datetime import datetime, timedelta
from telethon import TelegramClient, events
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2')
from telegram_bot import send_notification

api_id = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'
GROUP_ID = -1003769687656

LOG_FILE = 'signal_bot/signals_log.txt'
SIGNAL_TTL = timedelta(minutes=5)
CLEANUP_INTERVAL = 30  # seconds

client = TelegramClient('session', api_id, api_hash)

# Key: coin symbol, Value: {'side': ..., 'source': ..., 'time': datetime}
pending_signals = {}


def log_confluence(coin, side, source_a, source_b):
    msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CONFLUENCE | {coin} | {side} | {source_a} + {source_b}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg)


def process_signal(coin, side, source):
    now = datetime.now()
    existing = pending_signals.get(coin)

    if existing and existing['source'] != source and existing['side'] == side:
        # Confluence: same coin, same side, different source
        print(f"[VURKAÇ] CONFLUENCE! {coin} {side} - {existing['source']} + {source} ONAYLADI!")
        log_confluence(coin, side, existing['source'], source)
        del pending_signals[coin]
        send_notification(
            f"🎯 *VURKAÇ SİNYALİ!*\n"
            f"📌 {coin} | {side} | 4x\n"
            f"📊 EI + RSI ONAYLADI\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
            f"🔮 Hayali işlem açıldı!"
        )
    else:
        pending_signals[coin] = {'side': side, 'source': source, 'time': now}
        print(f"[BEKLİYOR] {source} | {coin} | {side} - Çift onay bekleniyor...")
        send_notification(
            f"👀 *TEK SİNYAL*\n"
            f"📌 {coin} | {side}\n"
            f"📊 Kaynak: {source}\n"
            f"⏳ Çift onay bekleniyor..."
        )


def parse_signal(text):
    signals = []

    al_idx = text.find('Yeni AL Sinyalleri')
    sat_idx = text.find('Yeni SAT Sinyalleri')
    rsi_idx = text.find('RSI Analizi')

    if al_idx != -1:
        al_end = sat_idx if sat_idx != -1 else len(text)
        al_section = text[al_idx:al_end]
        for coin in re.findall(r'\[([A-Z0-9]+USDT)\]', al_section):
            signals.append({'coin': coin, 'side': 'LONG', 'source': 'EI_SIGNAL'})

    if sat_idx != -1:
        sat_section = text[sat_idx:]
        for coin in re.findall(r'\[([A-Z0-9]+USDT)\]', sat_section):
            signals.append({'coin': coin, 'side': 'SHORT', 'source': 'EI_SIGNAL'})

    if rsi_idx != -1:
        rsi_section = text[rsi_idx:]
        for coin in re.findall(r'\[?\*?\*?([A-Z0-9]+USDT)\*?\*?\]?', rsi_section):
            signals.append({'coin': coin, 'side': 'LONG', 'source': 'RSI'})

    return signals


@client.on(events.NewMessage(chats=GROUP_ID))
async def handler(event):
    text = event.message.text
    if not text:
        return

    signals = parse_signal(text)
    for s in signals:
        process_signal(s['coin'], s['side'], s['source'])


async def cleanup_loop():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = datetime.now()
        stale = [coin for coin, data in pending_signals.items()
                 if now - data['time'] > SIGNAL_TTL]
        for coin in stale:
            print(f"[TEMİZLENDİ] {coin} sinyali 5 dakikada onaylanmadı, silindi.")
            del pending_signals[coin]


async def main():
    await client.start()
    print("Sinyal dinleyici başladı...")
    asyncio.create_task(cleanup_loop())
    await client.run_until_disconnected()

asyncio.run(main())
