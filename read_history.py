import asyncio
from telethon import TelegramClient
from datetime import datetime, timedelta

api_id = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'
GROUP_ID = -1003062732797

async def main():
    async with TelegramClient('session', api_id, api_hash) as client:
        two_months_ago = datetime.now() - timedelta(days=60)
        messages = []
        async for msg in client.iter_messages(GROUP_ID, offset_date=None, limit=500):
            if msg.date.replace(tzinfo=None) < two_months_ago:
                break
            if msg.text:
                messages.append({
                    'date': msg.date.strftime('%Y-%m-%d %H:%M'),
                    'text': msg.text[:200]
                })

        with open('ht_messages.txt', 'w', encoding='utf-8') as f:
            for m in messages:
                f.write(f"[{m['date']}] {m['text']}\n")
                f.write("-"*50 + "\n")

        print(f"Toplam {len(messages)} mesaj kaydedildi!")

asyncio.run(main())
