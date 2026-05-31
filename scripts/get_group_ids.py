import asyncio
from telethon import TelegramClient

api_id = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'

async def main():
    async with TelegramClient('session', api_id, api_hash) as client:
        async for dialog in client.iter_dialogs():
            print(f'{dialog.id} | {dialog.name}')

asyncio.run(main())
