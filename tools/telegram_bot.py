# -*- coding: utf-8 -*-
"""
MİNA v2 - Telegram Bot
"""

import os
import threading
from dotenv import load_dotenv
import telebot

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

def send_notification(message):
    """Telegram'a bildirim gönder - non-blocking"""
    def _send():
        try:
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            if chat_id:
                bot.send_message(chat_id, message, parse_mode='Markdown')
        except Exception as e:
            print(f"Telegram hatası: {e}")

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    return True

@bot.message_handler(commands=['start'])
def start(message):
    """Bot başlatma komutu"""
    chat_id = message.chat.id
    bot.reply_to(
        message,
        f"🤖 *MİNA v2 Trading Bot*\n\n"
        f"✅ Bot aktif!\n"
        f"📱 Chat ID: `{chat_id}`\n\n"
        f"Bu ID'yi .env dosyasına ekleyin!",
        parse_mode='Markdown'
    )
    print(f"\n{'='*50}")
    print(f"CHAT ID: {chat_id}")
    print(f"Bu ID'yi .env dosyasına TELEGRAM_CHAT_ID olarak ekleyin!")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    print("🤖 Telegram Bot başlatılıyor...")
    print("Bot'a /start yazın!")
    bot.polling()
