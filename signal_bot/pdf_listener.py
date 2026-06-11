import asyncio
import os
import sys
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)

api_id = 38446219
api_hash = '72a15e6baf9f4f79893dd122258e8bea'
GROUP_ID = -1003062732797

PDF_DIR = 'signal_bot/pdfs'
os.makedirs(PDF_DIR, exist_ok=True)

client = TelegramClient('session_pdf', api_id, api_hash)


@client.on(events.NewMessage(chats=GROUP_ID))
async def handler(event):
    msg = event.message
    if not msg.document:
        return

    if msg.document.mime_type != 'application/pdf':
        return

    # Extract original filename if available
    original_name = None
    for attr in msg.document.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            original_name = attr.file_name
            break

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{original_name}" if original_name else f"{timestamp}.pdf"
    filepath = os.path.join(PDF_DIR, filename)

    await client.download_media(msg, file=filepath)
    print(f"[PDF] Yeni PDF indirildi: {filename}")
    # PDF işleme yalnızca listener.py (mina-listener) üzerinden — çift pipeline kapalı.
    print("[PDF] İşleme atlandı — mina-listener devralır (pdf_listener devre dışı).")


async def main():
    await client.start()
    print("PDF dinleyici başladı...")
    await client.run_until_disconnected()


async def download_last_pdf():
    async with TelegramClient('session_pdf', api_id, api_hash) as client:
        print("Mesajlar taranıyor...")
        count = 0
        async for msg in client.iter_messages(GROUP_ID, limit=100):
            count += 1
            if msg.document:
                print(f"Doküman bulundu: {msg.document.mime_type}")
                if msg.document.mime_type == 'application/pdf':
                    os.makedirs('signal_bot/pdfs', exist_ok=True)
                    filename = f"signal_bot/pdfs/last_{msg.date.strftime('%Y%m%d_%H%M%S')}.pdf"
                    await client.download_media(msg, filename)
                    print(f"[PDF] İndirildi: {filename}")
                    break
        print(f"Toplam {count} mesaj tarandı, PDF bulunamadı.")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'last':
        asyncio.run(download_last_pdf())
    else:
        asyncio.run(main())
