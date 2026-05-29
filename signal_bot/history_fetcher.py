# -*- coding: utf-8 -*-
import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)

from telethon import TelegramClient
from telethon.errors import FloodWaitError

API_ID   = 38446219
API_HASH = '72a15e6baf9f4f79893dd122258e8bea'
SESSION  = 'session_ht'

GROUPS = [
    (-1003062732797, 'HT VIP BTC'),
    (-1001998444894, 'HTPLUS'),
    (-1001623533009, 'Haluk TATAR'),
]

DAYS     = 20
OUT_FILE = os.path.join(os.path.dirname(__file__), 'history', 'ht_history.txt')


async def fetch_group(client, group_id, group_name, since, messages):
    print(f"  Fetching {group_name} ({group_id})...")
    count = 0
    try:
        async for msg in client.iter_messages(group_id, offset_date=None, reverse=False):
            if msg.date.replace(tzinfo=timezone.utc) < since:
                break
            if not msg.text:
                continue
            ts   = msg.date.astimezone(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M')
            text = msg.text.replace('\n', ' ')
            messages.append((msg.date, f"[{ts}] [{group_name}] {text}\n"))
            count += 1
    except FloodWaitError as e:
        print(f"  FloodWait {e.seconds}s for {group_name}, sleeping...")
        await asyncio.sleep(e.seconds + 1)
    except Exception as e:
        print(f"  ERROR {group_name}: {e}")
    print(f"  {group_name}: {count} messages")


async def main():
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    print(f"Fetching last {DAYS} days (since {since.strftime('%Y-%m-%d %H:%M UTC')})...")

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    messages = []
    for gid, gname in GROUPS:
        await fetch_group(client, gid, gname, since, messages)
        await asyncio.sleep(1)

    await client.disconnect()

    messages.sort(key=lambda x: x[0])
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        for _, line in messages:
            f.write(line)

    print(f"\nDone. {len(messages)} total messages saved to {OUT_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
