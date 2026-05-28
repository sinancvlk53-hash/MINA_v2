# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import re
import datetime
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2')
sys.path.append('C:\\Users\\User\\Desktop\\MINA_v2\\backend')

from dotenv import load_dotenv
load_dotenv('C:\\Users\\User\\Desktop\\MINA_v2\\.env')

import telebot
from binance.enums import *
from config import BinanceConfig, AccountManager
from signal_bot.pdf_parser import parse_pdf_for_signals

TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID'))
LEVERAGE = 4

bot = telebot.TeleBot(TOKEN)

# ---------------------------------------------------------------------------
# Yardımcı — pozisyon aç
# ---------------------------------------------------------------------------

def get_precision(client, symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step = float(f['stepSize'])
                    step_str = str(step).rstrip('0')
                    return len(step_str.split('.')[-1]) if '.' in step_str else 0
    return 3


def open_position(client, account, symbol, side):
    bal       = account.get_usdt_balance()
    margin    = round((bal / 10) * 0.20, 2)

    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price  = float(ticker['price'])
    except Exception as e:
        return False, f"Fiyat alınamadı: {e}"

    prec  = get_precision(client, symbol)
    qty   = round((margin * LEVERAGE) / price, prec)
    oside = SIDE_BUY if side == 'LONG' else SIDE_SELL
    pside = 'LONG' if side == 'LONG' else 'SHORT'

    try:
        order = client.futures_create_order(
            symbol=symbol, side=oside,
            type=ORDER_TYPE_MARKET,
            quantity=qty, positionSide=pside
        )
        return True, f"OrderID:{order['orderId']} Qty:{qty} @{round(price,4)}"
    except Exception as e:
        err = str(e)
        if '-1109' in err:
            return False, "ATLANDI (-1109)"
        return False, err[:80]


# ---------------------------------------------------------------------------
# Ana onay akışı
# ---------------------------------------------------------------------------

def ask_approval(signals: list, pdf_time: str = None):
    """Sinyalleri Telegram'a gönder, cevap bekle."""
    if not signals:
        bot.send_message(CHAT_ID, "⚠️ PDF'de sinyal bulunamadı.")
        return

    try:
        _cfg = BinanceConfig()
        _cli = _cfg.get_client()
        positions  = _cli.futures_position_information()
        open_count = sum(1 for p in positions if float(p.get('positionAmt', 0)) != 0)
    except Exception:
        open_count = '?'

    lines = ["📄 *Yeni Haluk Tatar Sinyali!*\n"]
    if pdf_time:
        lines.append(f"⏰ PDF: {pdf_time}")
    lines.append(f"📊 Açık pozisyon: {open_count}/10 slot\n")

    for i, s in enumerate(signals, 1):
        lev  = s.get('leverage') or '3x'
        lev  = re.sub(r'^(\d+x)\d+$', r'\1', str(lev))
        tp1  = s.get('tp1') or '—'
        tp2  = s.get('tp2') or '—'
        stop = s.get('stop') or '—'
        lines.append(
            f"{i}️⃣ *{s['coin']}* | {s['side']} | "
            f"Giriş: ${s['entry']} | TP1: ${tp1}"
            + (f" | TP2: ${tp2}" if tp2 != '—' else "")
            + (f" | Stop: ${stop}" if stop != '—' else "")
            + f" | Kaldıraç: {lev}"
        )

    lines.append("\n✏️ Açmak istediklerini yaz:\n`1,3,5` veya `HEPSI` veya `HAYIR`")
    msg = bot.send_message(CHAT_ID, "\n".join(lines), parse_mode='Markdown')

    bot.register_next_step_handler(msg, lambda m: handle_reply(m, signals))


def handle_reply(message, signals):
    text = message.text.strip().upper()

    if text == 'HAYIR':
        bot.send_message(CHAT_ID, "❌ Sinyaller atlandı.")
        return

    if text == 'HEPSI':
        selected = list(range(len(signals)))
    else:
        try:
            selected = [int(x.strip()) - 1 for x in text.split(',')]
            selected = [i for i in selected if 0 <= i < len(signals)]
        except ValueError:
            bot.send_message(CHAT_ID, "⚠️ Geçersiz giriş. `1,3,5` ya da `HEPSI` ya da `HAYIR` yaz.")
            bot.register_next_step_handler(message, lambda m: handle_reply(m, signals))
            return

    if not selected:
        bot.send_message(CHAT_ID, "⚠️ Seçim geçersiz, sinyal açılmadı.")
        return

    config  = BinanceConfig()
    client  = config.get_client()
    account = AccountManager(client)

    results = []
    for i in selected:
        s = signals[i]
        symbol = s['coin']
        side   = s['side']
        ok, detail = open_position(client, account, symbol, side)
        icon = "✅" if ok else "❌"
        results.append(f"{icon} {symbol} {side}: {detail}")
        time.sleep(0.4)

    summary = "\n".join(results)
    bot.send_message(CHAT_ID, f"📊 *Sonuçlar:*\n{summary}", parse_mode='Markdown')


# ---------------------------------------------------------------------------
# PDF → onay akışı entegrasyonu
# ---------------------------------------------------------------------------

def process_new_pdf(pdf_path: str):
    """PDF'i parse et ve onay akışını başlat."""
    pdf_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    bot.send_message(CHAT_ID, f"📥 Yeni PDF alındı, analiz ediliyor...\n`{os.path.basename(pdf_path)}`",
                     parse_mode='Markdown')
    try:
        raw     = parse_pdf_for_signals(pdf_path)
        raw     = raw.strip().lstrip('```json').lstrip('```').rstrip('```').strip()
        signals = json.loads(raw)
        ask_approval(signals, pdf_time=pdf_time)
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ PDF parse hatası: {e}")


# ---------------------------------------------------------------------------
# Bağımsız çalıştırma — bot polling
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys as _sys
    print("Onay botu başlatıldı, polling...")

    if len(_sys.argv) > 1:
        # Doğrudan PDF verilebilir: python approval_bot.py dosya.pdf
        process_new_pdf(_sys.argv[1])

    bot.infinity_polling()
