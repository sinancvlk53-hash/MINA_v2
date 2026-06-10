# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import re
import datetime
import atexit
import threading
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)
sys.path.append(os.path.join(_ROOT, 'backend'))

LOCK_FILE = os.path.join(os.path.dirname(__file__), 'approval_bot.lock')

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

def _acquire_lock():
    if os.path.exists(LOCK_FILE):
        stale = False
        try:
            pid = int(open(LOCK_FILE, encoding='utf-8').read().strip())
        except (OSError, ValueError):
            stale = True
        else:
            if not _pid_alive(pid):
                stale = True
        if stale:
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        else:
            print(f"approval_bot zaten çalışıyor (PID {pid}). Çıkılıyor.")
            sys.exit(1)
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    atexit.register(_release_lock)

def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

import telebot
from binance.enums import *
from config import BinanceConfig, AccountManager
from signal_bot.signal_parser import parse_haluk_pdf_path, enqueue_haluk_pdf_records

TOKEN        = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID      = int(os.getenv('TELEGRAM_CHAT_ID'))
LEVERAGE     = 4
HT_QUEUE_FILE = os.path.join(os.path.dirname(__file__), 'ht_signals_queue.json')
RAW_QUEUE_FILE = os.path.join(os.path.dirname(__file__), 'raw_signal_queue.json')

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


def get_price_precision(client, symbol: str) -> int:
    """tickSize'dan fiyat ondalık basamak sayısını döndür."""
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    tick_str = str(float(f['tickSize'])).rstrip('0')
                    return len(tick_str.split('.')[-1]) if '.' in tick_str else 0
    return 2


# stop_levels.json → kök dizinde, engine ile paylaşılan D1 tetik fiyatları
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP_LEVELS_FILE    = os.path.join(_ROOT, 'stop_levels.json')
PENDING_ORDERS_FILE = os.path.join(_ROOT, 'pending_orders.json')

def _load_stop_levels() -> dict:
    try:
        with open(STOP_LEVELS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_stop_levels(data: dict) -> None:
    try:
        with open(STOP_LEVELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _load_pending_orders() -> dict:
    try:
        with open(PENDING_ORDERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_pending_orders(data: dict) -> None:
    try:
        with open(PENDING_ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _parse_price(val) -> float | None:
    """'75000' veya '74000-76000' formatındaki fiyatı float'a çevir (midpoint)."""
    if val is None:
        return None
    s = str(val).replace(',', '.').strip()
    if not s or s == '—':
        return None
    range_m = re.match(r'^(\d[\d.]*)\s*-\s*(\d[\d.]*)$', s)
    if range_m:
        try:
            lo, hi = float(range_m.group(1)), float(range_m.group(2))
            return (lo + hi) / 2
        except ValueError:
            pass
    try:
        return float(s)
    except ValueError:
        return None


def open_position(client, account, symbol, side, limit_price=None, stop_d1_price=None):
    """Pozisyon aç. limit_price verilirse LİMİT GTC, verilmezse MARKET emri kullanılır.
    stop_d1_price verilirse stop_levels.json'a D1 tetik fiyatı kaydedilir."""
    try:
        from mina_dashboard_settings import is_motor_paused
        if is_motor_paused():
            return False, "Motor pasif (dashboard ayarları)"
    except ImportError:
        pass
    bal    = account.get_usdt_balance()
    margin = round((bal / 10) * 0.20, 2)

    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    try:
        ticker       = client.futures_symbol_ticker(symbol=symbol)
        market_price = float(ticker['price'])
    except Exception as e:
        return False, f"Fiyat alınamadı: {e}"

    prec  = get_precision(client, symbol)
    oside = SIDE_BUY if side == 'LONG'  else SIDE_SELL
    pside = 'LONG'   if side == 'LONG'  else 'SHORT'

    parsed_limit = _parse_price(limit_price)
    use_limit    = parsed_limit is not None and parsed_limit > 0

    try:
        if use_limit:
            price_prec = get_price_precision(client, symbol)
            limit_px   = round(parsed_limit, price_prec)
            qty        = round((margin * LEVERAGE) / limit_px, prec)
            order      = client.futures_create_order(
                symbol=symbol, side=oside,
                type=ORDER_TYPE_LIMIT,
                price=limit_px,
                quantity=qty,
                positionSide=pside,
                timeInForce='GTC',
            )
            type_str = f"LİMİT @{limit_px}"
        else:
            qty   = round((margin * LEVERAGE) / market_price, prec)
            order = client.futures_create_order(
                symbol=symbol, side=oside,
                type=ORDER_TYPE_MARKET,
                quantity=qty,
                positionSide=pside,
            )
            type_str = f"MARKET @{round(market_price, 4)}"
    except Exception as e:
        err = str(e)
        if '-1109' in err:
            return False, "ATLANDI (-1109)"
        return False, err[:80]

    pos_key = f"{symbol}_{side}"

    # D1 tetik fiyatını engine için kaydet
    if stop_d1_price is not None:
        parsed_stop = _parse_price(stop_d1_price)
        if parsed_stop and parsed_stop > 0:
            sl          = _load_stop_levels()
            sl[pos_key] = float(round(parsed_stop, 8))
            _save_stop_levels(sl)

    # Limit emir ise 48h iptal takibine al
    if use_limit:
        po          = _load_pending_orders()
        po[pos_key] = {
            'order_id':  order['orderId'],
            'symbol':    symbol,
            'side':      side,
            'placed_at': time.time(),
        }
        _save_pending_orders(po)

    return True, f"OrderID:{order['orderId']} Qty:{qty} {type_str}"


# ---------------------------------------------------------------------------
# Ana onay akışı
# ---------------------------------------------------------------------------

def ask_approval(signals: list, pdf_time: str = None, source: str = 'PDF'):
    """Sinyalleri Telegram'a gönder, cevap bekle."""
    if not signals:
        bot.send_message(CHAT_ID, "⚠️ Sinyal bulunamadı.")
        return

    try:
        _cfg = BinanceConfig()
        _cli = _cfg.get_client()
        positions  = _cli.futures_position_information()
        open_count = sum(1 for p in positions if float(p.get('positionAmt', 0)) != 0)
    except Exception:
        open_count = '?'

    header = "📡 *Yeni HT VIP Sinyali!*" if source == 'HT' else "📄 *Yeni Haluk Tatar Sinyali!*"
    lines  = [f"{header}\n"]
    if pdf_time:
        label = "Sinyal" if source == 'HT' else "PDF"
        lines.append(f"⏰ {label}: {pdf_time}")
    lines.append(f"📊 Açık pozisyon: {open_count}/10 slot\n")

    for i, s in enumerate(signals, 1):
        lev   = s.get('leverage_label') or s.get('leverage') or ('5x' if source == 'HT' else '3x')
        lev   = re.sub(r'^(\d+)x?$', r'\1x', str(lev)) if str(lev).isdigit() else str(lev)
        lev   = re.sub(r'^(\d+x)\d+$', r'\1', str(lev))
        d1    = s.get('d1_price') or s.get('stop')
        entry = s.get('entry') or '—'
        tp1   = s.get('tp1')   or '—'
        tp2   = s.get('tp2')   or '—'
        stop  = s.get('stop')  or (str(d1) if d1 else '—')
        risk  = s.get('risk')  or ''
        ttype = s.get('trade_type') or ''
        extra = f" [{ttype}]" if ttype else ""
        extra += f" Risk:{risk}" if risk else ""
        lines.append(
            f"{i}️⃣ *{s['coin']}* | {s['side']} | "
            f"Giriş: {entry} | TP1: {tp1}"
            + (f" | TP2: {tp2}" if tp2 != '—' else "")
            + (f" | Stop: {stop}" if stop != '—' else "")
            + f" | {lev}{extra}"
        )

    lines.append("\n✏️ Açmak istediklerini yaz:\n`1,3,5` veya `HEPSI` veya `HAYIR`")
    msg = bot.send_message(CHAT_ID, "\n".join(lines), parse_mode='Markdown')

    bot.register_next_step_handler(msg, lambda m: handle_reply(m, signals))


def handle_reply(message, signals):
    # Komut gelirse next_step'i bypass et, normal handler'a ilet
    if message.text and message.text.startswith('/'):
        bot.process_new_messages([message])
        return

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
        s      = signals[i]
        symbol = s['coin']
        side   = s['side']
        entry  = s.get('entry')
        stop   = s.get('stop')
        ok, detail = open_position(client, account, symbol, side,
                                   limit_price=entry, stop_d1_price=stop)
        icon = "✅" if ok else "❌"
        results.append(f"{icon} {symbol} {side}: {detail}")
        time.sleep(0.4)

    summary = "\n".join(results)
    bot.send_message(CHAT_ID, f"📊 *Sonuçlar:*\n{summary}", parse_mode='Markdown')


# ---------------------------------------------------------------------------
# PDF → onay akışı entegrasyonu
# ---------------------------------------------------------------------------

def process_new_pdf(pdf_path: str):
    """PDF'i haluk_pdf_parser ile işle → raw_signal_queue → onay akışı."""
    from signal_bot.haluk_pdf_processed import is_pdf_processed

    basename = os.path.basename(pdf_path)
    if is_pdf_processed(pdf_path):
        print(f"[PDF] ATLA (listener zaten işledi): {basename}")
        return

    pdf_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    bot.send_message(CHAT_ID, f"📥 Yeni PDF alındı, analiz ediliyor...\n`{basename}`",
                     parse_mode='Markdown')
    try:
        records, pause = parse_haluk_pdf_path(pdf_path)
        enqueue_haluk_pdf_records(pdf_path, records)
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ PDF parse hatası: {e}")
        return

    if pause:
        kw = next((r.get('reject_reason', '') for r in records if r.get('symbol') == 'SYSTEM'), '?')
        msg = bot.send_message(
            CHAT_ID,
            f"⚠️ *HABER ALARMI* — Sistem PAUSE!\n"
            f"Tetikleyen: `{kw}`\n\n"
            f"Mimar manuel onayı: `DEVAM` veya `HAYIR`",
            parse_mode='Markdown',
        )
        bot.register_next_step_handler(msg, lambda m: _handle_news_alarm(m, pdf_path, pdf_time))
        return

    macro = [r for r in records if 'makro filtre' in str(r.get('reject_reason', ''))]
    if macro:
        bot.send_message(
            CHAT_ID,
            f"📊 *Makro F1:* {len(macro)} kayıt (işlem yok)",
            parse_mode='Markdown',
        )

    rejected = [r for r in records if r.get('status') == 'rejected' and 'UPDATE' in str(r.get('reject_reason', ''))]
    if rejected:
        bot.send_message(
            CHAT_ID,
            f"ℹ️ *UPDATE tuzağı* — {len(rejected)} bölüm reddedildi.",
            parse_mode='Markdown',
        )

    signals = [
        {
            'coin': r['symbol'],
            'side': r['direction'],
            'entry': str(r.get('entry_price') or '—'),
            'stop': str(r.get('stop_price') or '—'),
            'leverage': r.get('leverage'),
            'leverage_label': f"{r.get('leverage')}x",
            'd1_price': r.get('stop_price'),
        }
        for r in records if r.get('status') == 'approved'
    ]
    if not signals:
        bot.send_message(CHAT_ID, "⚠️ Onaylanan sinyal bulunamadı.")
        return

    ask_approval(signals, pdf_time=pdf_time)


def _handle_news_alarm(message, pdf_path: str, pdf_time: str):
    if message.text and message.text.startswith('/'):
        bot.process_new_messages([message])
        return
    text = message.text.strip().upper()
    if text == 'DEVAM':
        bot.send_message(CHAT_ID, "✅ Manuel onay verildi. Sinyaller yeniden işleniyor...")
        try:
            raw     = _reparse_signals(pdf_path)
            signals = json.loads(raw.strip().lstrip('```json').lstrip('```').rstrip('```').strip())
            ask_approval(signals, pdf_time=pdf_time)
        except Exception as e:
            bot.send_message(CHAT_ID, f"❌ Yeniden parse hatası: {e}")
    else:
        bot.send_message(CHAT_ID, "❌ İşlem atlandı.")


def _reparse_signals(pdf_path: str) -> str:
    """Filtre atlayarak sadece sinyal çıkarımı yapar (haber alarmı sonrası DEVAM için)."""
    import base64
    import anthropic as _ant
    with open(pdf_path, 'rb') as f:
        pdf_data = base64.standard_b64encode(f.read()).decode('utf-8')
    client = _ant.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data}},
                {"type": "text", "text": """Bu PDF bir kripto trading analiz raporu.
Sadece şunları çıkar ve JSON formatında ver:
- coin: sembol (örn: BTCUSDT, XRPUSDT)
- side: LONG veya SHORT
- entry: giriş fiyatı veya bölgesi
- tp1: birinci hedef
- tp2: ikinci hedef (varsa)
- stop: stop loss (varsa)
- leverage: kaldıraç (varsa)

Sadece JSON array döndür, başka hiçbir şey yazma.
Örnek: [{"coin":"BTCUSDT","side":"LONG","entry":"75000","tp1":"78000","tp2":"81000","stop":"72000","leverage":"3x"}]"""}
            ]
        }]
    )
    return msg.content[0].text


# ---------------------------------------------------------------------------
# HT sinyal kuyruğu izleyici
# ---------------------------------------------------------------------------

def _is_haluk_pdf_source(source) -> bool:
    s = str(source or "")
    return s == "haluk_pdf" or s.upper().startswith("HALUK_PDF")


def _normalize_queue_signal(sig: dict) -> dict:
    """ht_signals_queue haluk_pdf (symbol/direction) ve legacy coin/side birleştir."""
    out = dict(sig)
    out["coin"] = sig.get("coin") or sig.get("symbol") or ""
    out["side"] = sig.get("side") or sig.get("direction") or ""
    entry = sig.get("entry")
    if entry in (None, "", "—"):
        ep = sig.get("entry_price")
        if ep is not None:
            entry = str(ep)
    out["entry"] = entry or "—"
    stop = sig.get("stop")
    if stop in (None, "", "—"):
        sp = sig.get("stop_price")
        if sp is not None:
            stop = str(sp)
    out["stop"] = stop or "—"
    out.setdefault("leverage_label", "4x")
    return out


def _auto_execute_haluk_pdf_signals(signals: list, pdf_time: str = "") -> None:
    """haluk_pdf kaynaklı sinyaller — Telegram onayı beklemeden aç."""
    if not signals:
        return
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    results = []
    for raw in signals:
        s = _normalize_queue_signal(raw)
        symbol = s.get("coin") or s.get("symbol")
        side = s.get("side") or s.get("direction")
        if not symbol or side not in ("LONG", "SHORT"):
            results.append(f"❌ {symbol or '?'}: geçersiz sembol/yön")
            continue
        ok, detail = open_position(
            client,
            account,
            symbol,
            side,
            limit_price=s.get("entry"),
            stop_d1_price=s.get("stop"),
        )
        icon = "✅" if ok else "❌"
        results.append(f"{icon} {symbol} {side}: {detail}")
        time.sleep(0.4)

    header = "📄 *Haluk PDF — otomatik onay*\n"
    if pdf_time:
        header += f"⏰ {pdf_time}\n"
    summary = "\n".join(results)
    try:
        bot.send_message(CHAT_ID, header + summary, parse_mode="Markdown")
    except Exception as exc:
        print(f"[QUEUE] haluk_pdf Telegram özeti: {exc}")
    print(f"[QUEUE] haluk_pdf otomatik açılış: {len(signals)} sinyal")


def _consume_queue_file(path: str, default_source: str = 'HT'):
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    # Yeni format: entries[] (signal_parser)
    entries = data.get('entries', [])
    if entries:
        haluk_auto = []
        manual = []
        consumed_symbols = set()
        for e in entries:
            if e.get('symbol') == 'SYSTEM':
                continue
            src = e.get('source')
            sym = e.get('symbol')
            if _is_haluk_pdf_source(src):
                consumed_symbols.add(sym)
                haluk_auto.append({
                    'coin': e['symbol'],
                    'side': e['direction'],
                    'entry': str(e.get('entry_price') or '—'),
                    'stop': str(e.get('stop_price') or '—'),
                    'leverage': e.get('leverage'),
                    'leverage_label': f"{e.get('leverage')}x" if e.get('leverage') else '4x',
                    'd1_price': e.get('stop_price'),
                    'source': src,
                })
            elif e.get('status') == 'approved':
                consumed_symbols.add(sym)
                manual.append({
                    'coin': e['symbol'],
                    'side': e['direction'],
                    'entry': str(e.get('entry_price') or '—'),
                    'stop': str(e.get('stop_price') or '—'),
                    'leverage': e.get('leverage'),
                    'leverage_label': f"{e.get('leverage')}x",
                    'd1_price': e.get('stop_price'),
                    'source': e.get('source'),
                })

        if haluk_auto:
            print(f"[QUEUE] {len(haluk_auto)} haluk_pdf otomatik (entries) ← {path}")
            _auto_execute_haluk_pdf_signals(haluk_auto, pdf_time=data.get('updated_at', ''))

        if manual:
            src = 'HT' if any('haluk' in str(s.get('source', '')) for s in manual) else 'PDF'
            print(f"[QUEUE] {len(manual)} sinyal (entries) ← {path}")
            ask_approval(manual, pdf_time=data.get('updated_at', ''), source=src)

        data['entries'] = [
            e for e in entries
            if e.get('symbol') not in consumed_symbols or e.get('symbol') == 'SYSTEM'
        ]
        if data['entries']:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            os.remove(path)
        return

    os.remove(path)
    if data.get('system_pause'):
        print(f"[QUEUE] PAUSE — {data.get('pause_keyword')}")
        return
    signals = data.get('signals', [])
    source_info = data.get('source', default_source)
    if not signals:
        return

    haluk_auto = []
    manual = []
    for s in signals:
        src = s.get('source') or source_info
        if _is_haluk_pdf_source(src) or _is_haluk_pdf_source(source_info):
            item = dict(s)
            item['status'] = 'approved'
            item['source'] = item.get('source') or 'haluk_pdf'
            haluk_auto.append(_normalize_queue_signal(item))
        else:
            manual.append(s)

    if haluk_auto:
        print(f"[QUEUE] {len(haluk_auto)} haluk_pdf otomatik ← {path}")
        _auto_execute_haluk_pdf_signals(haluk_auto, pdf_time=source_info)

    if manual:
        src = 'HT' if 'HT' in str(source_info).upper() else 'PDF'
        print(f"[QUEUE] {len(manual)} sinyal ← {path}")
        ask_approval(manual, pdf_time=source_info, source=src)


def _ht_queue_checker():
    """Arka planda 5 sn'de bir HT + RAW SIGNAL kuyruklarını kontrol eder."""
    while True:
        time.sleep(5)
        for qpath in (RAW_QUEUE_FILE, HT_QUEUE_FILE):
            try:
                _consume_queue_file(qpath)
            except Exception as e:
                print(f"[QUEUE] {qpath} hata: {e}")


# ---------------------------------------------------------------------------
# Telegram komut işleyicileri (/snapshot /durum /kapat /bakiye)
# ---------------------------------------------------------------------------

def _only_owner(message):
    return message.chat.id == CHAT_ID


@bot.message_handler(commands=['snapshot'])
def cmd_snapshot(message):
    if not _only_owner(message):
        return
    try:
        config    = BinanceConfig()
        client    = config.get_client()
        account   = AccountManager(client)
        bal       = account.get_usdt_balance()
        positions = [p for p in client.futures_position_information()
                     if float(p['positionAmt']) != 0]
        if not positions:
            bot.send_message(CHAT_ID, f"*Bakiye: ${bal:.2f}*\nAcik pozisyon yok.", parse_mode='Markdown')
            return
        lines = [f"*Bakiye: ${bal:.2f} | {len(positions)} pozisyon*\n"]
        for p in sorted(positions, key=lambda x: x['symbol']):
            sym   = p['symbol']
            side  = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
            lev   = int(p['leverage'])
            entry = float(p['entryPrice'])
            pnl   = float(p['unRealizedProfit'])
            iso   = float(p['isolatedMargin'])
            roe   = (pnl / iso * 100) if iso > 0 else 0
            icon  = '🟢' if pnl >= 0 else '🔴'
            lines.append(
                f"{icon} *{sym}* {side} {lev}x\n"
                f"   Giris: {entry:.4f} | PnL: ${pnl:+.2f} | ROE: {roe:+.1f}%"
            )
        bot.send_message(CHAT_ID, "\n".join(lines), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(CHAT_ID, f"Snapshot hatasi: {e}")


@bot.message_handler(commands=['bakiye'])
def cmd_bakiye(message):
    if not _only_owner(message):
        return
    try:
        config  = BinanceConfig()
        client  = config.get_client()
        account = AccountManager(client)
        bal     = account.get_usdt_balance()
        bot.send_message(CHAT_ID, f"*Bakiye: ${bal:.2f} USDT*", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(CHAT_ID, f"Bakiye hatasi: {e}")


@bot.message_handler(commands=['durum'])
def cmd_durum(message):
    if not _only_owner(message):
        return
    try:
        import psutil
        targets = {
            'engine':         'main.py',
            'approval_bot':   'approval_bot.py',
            'ht_listener':    'ht_listener.py',
            'pdf_listener':   'pdf_listener.py',
            'listener':       'signal_bot/listener.py',
            'merter_tracker': 'merter_tracker.py',
        }
        running = set()
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                for key, script in targets.items():
                    if script in cmdline:
                        running.add(key)
            except Exception:
                pass
        lines = ['*Servis Durumu:*\n']
        for key in targets:
            icon  = '🟢' if key in running else '🔴'
            state = 'aktif' if key in running else 'KAPALI'
            lines.append(f"{icon} {key}: {state}")
        bot.send_message(CHAT_ID, "\n".join(lines), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(CHAT_ID, f"Durum hatasi: {e}")


@bot.message_handler(commands=['kapat'])
def cmd_kapat(message):
    if not _only_owner(message):
        return
    try:
        config    = BinanceConfig()
        client    = config.get_client()
        positions = [p for p in client.futures_position_information()
                     if float(p['positionAmt']) != 0]
        if not positions:
            bot.send_message(CHAT_ID, "Acik pozisyon yok.")
            return
        lines = [f"*{len(positions)} pozisyon kapatilacak:*\n"]
        for p in sorted(positions, key=lambda x: x['symbol']):
            sym  = p['symbol']
            side = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
            pnl  = float(p['unRealizedProfit'])
            lines.append(f"• {sym} {side} | PnL: ${pnl:+.2f}")
        lines.append("\nOnaylamak icin *ONAYLA* yaz.")
        msg = bot.send_message(CHAT_ID, "\n".join(lines), parse_mode='Markdown')
        bot.register_next_step_handler(msg, lambda m: _handle_kapat_confirm(m, client, positions))
    except Exception as e:
        bot.send_message(CHAT_ID, f"Kapat hatasi: {e}")


def _handle_kapat_confirm(message, client, positions):
    if not _only_owner(message):
        return
    if message.text and message.text.startswith('/'):
        bot.process_new_messages([message])
        return
    if message.text.strip().upper() != 'ONAYLA':
        bot.send_message(CHAT_ID, "Iptal edildi.")
        return
    results = []
    for p in positions:
        sym    = p['symbol']
        amt    = float(p['positionAmt'])
        side   = 'LONG' if amt > 0 else 'SHORT'
        qty    = abs(amt)
        oside  = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pside  = side
        try:
            order = client.futures_create_order(
                symbol=sym, side=oside,
                type=ORDER_TYPE_MARKET,
                quantity=qty,
                positionSide=pside,
            )
            results.append(f"✅ {sym} {side} kapatildi")
        except Exception as e:
            results.append(f"❌ {sym}: {str(e)[:60]}")
        time.sleep(0.3)
    bot.send_message(CHAT_ID, "\n".join(results))


# ---------------------------------------------------------------------------
# Bağımsız çalıştırma — bot polling
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys as _sys
    _acquire_lock()
    threading.Thread(target=_ht_queue_checker, daemon=True).start()
    print(f"Onay botu başlatıldı (PID {os.getpid()}), polling + HT kuyruk izleyici aktif...")

    if len(_sys.argv) > 1:
        # Doğrudan PDF verilebilir: python approval_bot.py dosya.pdf
        process_new_pdf(_sys.argv[1])

    bot.infinity_polling()
