import asyncio
import re
import sys
from datetime import datetime
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2')
from telethon import TelegramClient, events
from telegram_bot import send_notification

api_id = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'
HT_GROUP_ID = -1003062732797

client = TelegramClient('session_ht', api_id, api_hash)

def parse_ht_signal(text):
    signals = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        long_match = re.search(r'([A-Z]{2,10}USDT?).*[Ll]ong', line)
        short_match = re.search(r'([A-Z]{2,10}USDT?).*[Ss]hort', line)

        if long_match:
            coin = long_match.group(1)
            if not coin.endswith('USDT'):
                coin = coin + 'USDT'
            signals.append({'coin': coin, 'side': 'LONG', 'source': 'HT'})
        elif short_match:
            coin = short_match.group(1)
            if not coin.endswith('USDT'):
                coin = coin + 'USDT'
            signals.append({'coin': coin, 'side': 'SHORT', 'source': 'HT'})

    return signals

@client.on(events.NewMessage(chats=HT_GROUP_ID))
async def handler(event):
    text = event.message.text
    if not text:
        return

    signals = parse_ht_signal(text)
    for s in signals:
        print(f"[HT SİNYAL] {s['coin']} | {s['side']}")
        send_notification(
            f"📡 *HT VIP BTC SİNYALİ*\n"
            f"📌 {s['coin']} | {s['side']}\n"
            f"👤 Haluk Tatar\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

async def main():
    await client.start()
    print("HT sinyal dinleyici başladı...")
    await client.run_until_disconnected()

asyncio.run(main())
