# -*- coding: utf-8 -*-
"""
MİNA v2 - Execution Engine - LOGGING İLE
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BinanceConfig, AccountManager
from binance.enums import *
import time
import json
import re
import traceback
from datetime import datetime
import logging

try:
    from telegram_bot import send_notification
except Exception:
    def send_notification(_):
        return False

# ═══════════════════════════════════════════════
# LOGGING KURULUMU
# ═══════════════════════════════════════════════

# Log formatı
log_format = '[%(asctime)s] %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'
""
# Logger oluştur
logger = logging.getLogger('MİNA_v2')
logger.setLevel(logging.INFO)

# Dosyaya yazma
file_handler = logging.FileHandler('mina_bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format, date_format))

# Konsola yazma
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format, date_format))

# Handler'ları ekle
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ═══════════════════════════════════════════════

# Tracking dosyaları
DEFENSE_FILE       = "defense_levels.json"
TP_FILE            = "tp_levels.json"
MAX_PRICE_FILE     = "max_prices.json"
INITIAL_MARGIN_FILE = "initial_margins.json"
STOP_LEVELS_FILE    = "stop_levels.json"
PENDING_ORDERS_FILE  = "pending_orders.json"
TP_STOP_FILE         = "tp_stop_orders.json"
INITIAL_QTY_FILE     = "initial_qtys.json"
D2_BE_FILE           = "d2_be_orders.json"
LIMIT_ORDER_TTL_H   = 48

# Özel kaldıraç kuralları
LEVERAGE_RULES = {
    1:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard'},
    2:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard'},
    3:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard'},
    4:  {'stop_loss': None, 'defense_count': 3, 'tp_type': 'standard'},
    5:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard'},
    10: {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'fast'}
}

def load_json(filename):
    """JSON dosyasını yükle"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    """JSON dosyasına kaydet"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"❌ JSON yazma hatası ({filename}): {e}")

# exchange_info cache — her pozisyon için tekrar çekilmemesi için
_exchange_info_cache = {}
_max_qty_cache = {}

def get_symbol_max_qty(client, symbol):
    """Sembol için maxQty'yi cache'li getir.
    MARKET_LOT_SIZE maxQty=0 ise LOT_SIZE maxQty'ye fallback yapar.
    Bazı semboller (DYMUSDT vb.) MARKET_LOT_SIZE'da 0 döndürür → -4005 hatası."""
    if symbol in _max_qty_cache:
        return _max_qty_cache[symbol]
    exchange_info = client.futures_exchange_info()
    for s in exchange_info['symbols']:
        sym = s['symbol']
        market_max = 0.0
        lot_max    = 0.0
        for f in s['filters']:
            if f['filterType'] == 'MARKET_LOT_SIZE':
                market_max = float(f['maxQty'])
            elif f['filterType'] == 'LOT_SIZE':
                lot_max = float(f['maxQty'])
        if market_max > 0:
            max_qty = market_max
        elif lot_max > 0:
            max_qty = lot_max
        else:
            max_qty = float('inf')
        _max_qty_cache[sym] = max_qty
    return _max_qty_cache.get(symbol, float('inf'))

def get_symbol_precision(client, symbol):
    """Sembol için lot size precision'ını cache'li getir"""
    if symbol in _exchange_info_cache:
        return _exchange_info_cache[symbol]
    exchange_info = client.futures_exchange_info()
    for s in exchange_info['symbols']:
        sym = s['symbol']
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                step_str = str(step_size).rstrip('0')
                prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
                _exchange_info_cache[sym] = prec
                break
    return _exchange_info_cache.get(symbol, 3)

def get_open_positions(client):
    """Açık pozisyonları getir"""
    positions = client.futures_position_information()
    open_pos = []
    for p in positions:
        if float(p['positionAmt']) != 0:
            open_pos.append(p)
    return open_pos

def calculate_pnl_percent(entry_price, current_price, side):
    """PnL yüzde hesapla"""
    if side == 'LONG':
        return ((current_price - entry_price) / entry_price) * 100
    else:
        return ((entry_price - current_price) / entry_price) * 100

def send_stop_loss_order(client, symbol, side, amount):
    """Stop Loss emri gönder — max qty aşılırsa chunk'lara böler"""
    try:
        precision = get_symbol_precision(client, symbol)
        max_qty   = get_symbol_max_qty(client, symbol)
        quantity  = round(amount, precision)

        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pos_side   = 'LONG' if side == 'LONG' else 'SHORT'

        if quantity <= max_qty:
            chunks = [quantity]
        else:
            chunk = round(max_qty, precision)
            chunks = []
            remaining = quantity
            while remaining > 0:
                c = round(min(chunk, remaining), precision)
                if c == 0:
                    break
                chunks.append(c)
                remaining = round(remaining - c, precision)

        order_ids = []
        for c in chunks:
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=c,
                positionSide=pos_side,
            )
            order_ids.append(str(order['orderId']))

        ids_str = ', '.join(order_ids)
        logger.info(f"🛑 STOP LOSS: {symbol} {side} - {quantity} kapatıldı ({len(chunks)} emir) - Orders: {ids_str}")
        return True, f"🛑 STOP LOSS: Tüm pozisyon kapatıldı ({quantity})"

    except Exception as e:
        error_str = str(e)
        if '-1106' in error_str:
            logger.warning(f"⚠️ STOP LOSS ATILDI: {symbol} {side} - Pozisyon zaten kapalı, takipten siliniyor.")
            return False, "POSITION_CLOSED"
        logger.error(f"❌ STOP LOSS HATASI: {symbol} {side} - {error_str}")
        return False, f"Hata: {error_str}"

# KAR ALMA STRATEJİSİ:
#   Standard (1x-5x):
#     TP1 (+3%): Orijinal girişin %50'si kapatılır. Giriş fiyatına stop order gönderilir.
#     TP2 (+5%): Kalan miktarın %50'si kapatılır. Trailing başlar (TP2 fiyatından).
#     Trailing : TP2 sonrası zirveyi takip eder. -%1.5 geri çekilince kalan tümü kapatılır.
#   Fast (10x):
#     TP1 (+2%): Orijinal girişin %50'si kapatılır. Giriş fiyatına stop order gönderilir.
#     TP2 (+4%): Kalan miktarın TAMAMI kapatılır. Trailing YOK.
def send_tp_order(client, symbol, side, current_amount, tp_level, initial_amount=None, tp_type='standard'):
    """Take Profit emri gönder"""
    try:
        if tp_level == 1:
            # Orijinal giris miktarinin %50'si (defense sonrasi DCA miktarindan bagimsiz)
            base = initial_amount if initial_amount is not None else current_amount
            close_amount = base * 0.50
            close_percent = 0.50
        elif tp_level == 2:
            # 10x: tamamini kapat (trailing yok); diger: %50 kapat (trailing baslar)
            close_percent = 1.00 if tp_type == 'fast' else 0.50
            close_amount = current_amount * close_percent
        elif tp_level == 3:
            close_percent = 1.00
            close_amount = current_amount * close_percent
        else:
            return False, "Geçersiz TP level"
        precision = get_symbol_precision(client, symbol)
        quantity = round(close_amount, precision)

        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY

        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )

        if tp_level == 3:
            logger.info(f"🎯 TRAILING STOP: {symbol} {side} - {quantity} kapatıldı - Order: {order['orderId']}")
            return True, f"🎯 TRAILING: {quantity} kapatıldı"
        else:
            logger.info(f"💰 TP{tp_level}: {symbol} {side} - {quantity} kapatıldı ({close_percent*100:.0f}%) - Order: {order['orderId']}")
            return True, f"TP{tp_level}: {quantity} kapatıldı ({close_percent*100:.0f}%)"

    except Exception as e:
        error_str = str(e)
        if '-1106' in error_str:
            logger.warning(f"⚠️ TP{tp_level} ATILDI: {symbol} {side} - Pozisyon zaten kapalı veya reduceOnly geçersiz. Takipten siliniyor.")
            return False, "POSITION_CLOSED"
        elif '-4003' in error_str:
            logger.warning(f"⚠️ TP{tp_level} ATILDI: {symbol} {side} - Miktar sıfır veya negatif (-4003), pozisyon zaten kapanmış. Takipten siliniyor.")
            return False, "POSITION_CLOSED"
        elif '-1109' in error_str:
            logger.warning(f"⚠️ {symbol} {side} hedge mode desteklemiyor (-1109), pozisyon takipten çıkarılıyor")
            return False, "HEDGE_NOT_SUPPORTED"
        logger.error(f"❌ TP{tp_level} HATASI: {symbol} {side} - {error_str}")
        return False, f"Hata: {error_str}"

def send_tp1_stop_order(client, symbol, side, entry_price, remaining_qty):
    try:
        precision  = get_symbol_precision(client, symbol)
        quantity   = round(remaining_qty, precision)
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pos_side   = 'LONG'   if side == 'LONG' else 'SHORT'
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type='STOP_MARKET',
            stopPrice=entry_price,
            quantity=quantity,
            positionSide=pos_side,
            reduceOnly=True,
        )
        order_id = order['orderId']
        logger.info(f"Stop order gonderildi: {symbol} {side} stopPrice={entry_price} qty={quantity} orderId={order_id}")
        return True, order_id
    except Exception as e:
        logger.error(f"Stop order hatasi: {symbol} {side} — {str(e)}")
        return False, None


def cancel_tp1_stop_order(client, pos_key, tp_stop_orders):
    info = tp_stop_orders.get(pos_key)
    if not info:
        return
    try:
        client.futures_cancel_order(symbol=info['symbol'], orderId=info['order_id'])
        logger.info(f"Stop order iptal edildi: {pos_key} orderId={info['order_id']}")
    except Exception as e:
        err = str(e)
        if '-2011' in err:
            logger.info(f"Stop order zaten dolmus/iptal: {pos_key} orderId={info['order_id']}")
        else:
            logger.error(f"Stop order iptal hatasi: {pos_key} — {err}")
    tp_stop_orders.pop(pos_key, None)


def send_d2_be_order(client, symbol, side, quantity, be_price):
    try:
        precision  = get_symbol_precision(client, symbol)
        qty        = round(quantity, precision)
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pos_side   = 'LONG'   if side == 'LONG' else 'SHORT'
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=round(be_price, 6),
            quantity=qty,
            positionSide=pos_side,
            reduceOnly=True,
        )
        order_id = order['orderId']
        logger.info(f"D2 BE order gonderildi: {symbol} {side} stopPrice={be_price:.6f} qty={qty} orderId={order_id}")
        return True, order_id
    except Exception as e:
        logger.error(f"D2 BE order hatasi: {symbol} {side} — {str(e)}")
        return False, None


def cancel_d2_be_order(client, pos_key, d2_be_orders):
    info = d2_be_orders.get(pos_key)
    if not info:
        return
    try:
        client.futures_cancel_order(symbol=info['symbol'], orderId=info['order_id'])
        logger.info(f"D2 BE order iptal edildi: {pos_key} orderId={info['order_id']}")
    except Exception as e:
        err = str(e)
        if '-2011' in err:
            logger.info(f"D2 BE order zaten dolmus/iptal: {pos_key} orderId={info['order_id']}")
        else:
            logger.error(f"D2 BE order iptal hatasi: {pos_key} — {err}")
    d2_be_orders.pop(pos_key, None)


MAX_RETRY      = 3    # Sipariş yeniden deneme sayısı
RETRY_DELAY    = 5    # Denemeler arası bekleme (saniye)
SLOT_CAP_RATIO = 0.98 # Slot'un kullanılabilir oranı (%98 — %2 güvenlik tamponu)

def _slot_limit_check(client, symbol, side, amount_usdt, label):
    """
    v1.4 Slot limit kontrolü:
    Bakiyeyi taze çek → slot = bakiye/10 * 0.98
    Mevcut margin + yeni miktar > slot ise False döner.
    """
    account = AccountManager(client)
    fresh_balance = account.get_usdt_balance()
    slot_cap = (fresh_balance / 10) * SLOT_CAP_RATIO

    pos_info = client.futures_position_information(symbol=symbol)
    current_margin = 0.0
    for p in pos_info:
        amt = float(p.get('positionAmt', 0))
        pos_side = 'LONG' if amt > 0 else 'SHORT'
        if p['symbol'] == symbol and pos_side == side and amt != 0:
            current_margin = float(p.get('isolatedMargin', 0))
            break

    projected = current_margin + amount_usdt
    if projected > slot_cap:
        logger.warning(
            f"⛔ {label} SLOT LİMİTİ v1.4: {symbol} {side} — "
            f"Margin {current_margin:.2f}$ + {amount_usdt:.2f}$ = {projected:.2f}$ "
            f"> Slot cap {slot_cap:.2f}$ (bakiye {fresh_balance:.2f}$ × 0.98/10). İptal."
        )
        return False, slot_cap
    return True, slot_cap


def _execute_with_retry(fn, label, symbol, side):
    """
    Fix 2 — Yeniden deneme:
    Başarısız sipariş → 5sn bekle → tekrar dene → 3 denemede olmadı → alarm.
    """
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            return fn()
        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRY:
                logger.warning(
                    f"⏳ {label} DENEME {attempt}/{MAX_RETRY}: {symbol} {side} — "
                    f"{last_err[:80]}. {RETRY_DELAY}s bekleniyor..."
                )
                time.sleep(RETRY_DELAY)
            else:
                logger.error(
                    f"❌ {label} {MAX_RETRY} DENEMEDE BAŞARISIZ: {symbol} {side} — {last_err}"
                )
                send_notification(
                    f"🚨 *ALARM — {label} BAŞARISIZ!*\n"
                    f"📌 {symbol} {side}\n"
                    f"❌ {MAX_RETRY} denemede gerçekleşmedi\n"
                    f"🔴 Son hata: {last_err[:120]}"
                )
    raise Exception(last_err)


# D1 DEFANS STRATEJİSİ (rakamlar örnek, oranlar sabittir):
#
# Giriş: 10.000$, 20 USDT kontrat (Total Size = %100)
# Kalan 80 USDT defans için kenarda bekler.
#
# D1 tetiklenir (-5% ROE):
#   Fiyat 9.500$'a düşer
#   15 USDT kontrat eklenir (DCA)
#   Yeni ortalama: (20×10.000 + 15×9.500) / 35 = 9.785$
#   Binance entryPrice otomatik güncellenir
#   TP seviyeleri yeni ortalamaya göre otomatik hesaplanır
#
# Kar alma (yeni ortalama 9.785$ üzerinden):
#   TP1: 9.785$ × 1.03 = 10.078$ → 0.50 × Total Size kapat
#        → Stop-loss 9.785$'a çek (pozisyon artık risksiz)
#   TP2: 9.785$ × 1.05 = 10.274$ → 0.25 × Total Size kapat
#   Trailing: kalan 0.25 × Total Size, tepeden -%1'de kapat
#
# ALTIN KURAL:
#   Fiyat D1 sonrası eski giriş fiyatına (10.000$) dönmeden
#   TP1 ve TP2 zaten tetiklenir. Yani D1 ceza değil, fırsata dönüşür.
def send_defense_order(client, symbol, side, defense_level, leverage):
    """Savunma emri gönder — v1.4 (slot limit + retry + alarm)"""
    try:
        account = AccountManager(client)
        balance = account.get_usdt_balance()
        slot_size = balance / 10

        rules = LEVERAGE_RULES.get(leverage)

        if not rules or not rules.get('defense_count'):
            return False, "Bu kaldıraçta savunma yok"

        if leverage in [4, 5]:
            defense_amounts = {
                1: slot_size * 0.20,  # D1: slot/5 (DCA)
                2: slot_size * 0.20,   # D2: slot/5 USDT (DCA) + TP iptal → break-even modu
                3: slot_size * 0.30   # D3: slot'un %30'u, sadece margin ekle
            }
        else:
            return False, "Savunma tanımsız"

        amount_usdt = defense_amounts.get(defense_level, 0)
        if amount_usdt == 0:
            return False, "Geçersiz defense level"

        # ── FIX 1+3: SLOT LİMİTİ v1.4 — taze bakiye + %2 tampon ────────────
        label = f"SAVUNMA {defense_level}"
        ok, slot_cap = _slot_limit_check(client, symbol, side, amount_usdt, label)
        if not ok:
            return False, "SLOT_LIMIT"
        # ─────────────────────────────────────────────────────────────────────

        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        max_defense = rules.get('defense_count', 0)

        if defense_level == max_defense:
            # D3 — margin ekle
            pos_side = 'LONG' if side == 'LONG' else 'SHORT'

            def do_margin():
                return client.futures_change_position_margin(
                    symbol=symbol,
                    positionSide=pos_side,
                    amount=amount_usdt,
                    type=1
                )

            # FIX 2 — retry
            _execute_with_retry(do_margin, label, symbol, side)
            logger.info(f"🛡️  SAVUNMA {defense_level}: {symbol} {side} - {amount_usdt:.2f} USDT MARGIN eklendi")
            return True, f"Savunma {defense_level}: {amount_usdt:.2f} USDT margin eklendi"

        # D1/D2 — kontrakt ekle
        position_size = amount_usdt * leverage
        raw_qty = position_size / price
        precision = get_symbol_precision(client, symbol)
        quantity = round(raw_qty, precision)
        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        pos_side_str = 'LONG' if side == 'LONG' else 'SHORT'

        max_qty = get_symbol_max_qty(client, symbol)
        chunks = []
        if quantity > max_qty:
            remaining = quantity
            while remaining > 0:
                chunk = round(min(remaining, max_qty), precision)
                if chunk == 0:
                    break
                chunks.append(chunk)
                remaining = round(remaining - chunk, precision)
        else:
            chunks = [quantity]

        last_order = None
        for chunk_qty in chunks:
            _chunk = chunk_qty
            def do_order(_q=_chunk):
                return client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=_q,
                    positionSide=pos_side_str
                )
            last_order = _execute_with_retry(do_order, label, symbol, side)

        logger.info(f"🛡️  SAVUNMA {defense_level}: {symbol} {side} - {quantity} eklendi (${amount_usdt:.2f}) - {len(chunks)} parça - Order: {last_order['orderId']}")
        return True, f"Savunma {defense_level}: {quantity} eklendi (${amount_usdt:.2f})"

    except Exception as e:
        error_str = str(e)
        if '-1106' in error_str:
            logger.warning(f"⚠️ SAVUNMA {defense_level} ATILDI: {symbol} {side} - Pozisyon kapalı, temizleniyor.")
            return False, "POSITION_CLOSED"
        if '-4054' in error_str:
            logger.error(f"❌ SAVUNMA {defense_level} MARGIN HATASI -4054: {symbol} {side} - {error_str}")
            return False, "MARGIN_FAILED"
        logger.error(f"❌ SAVUNMA {defense_level} HATASI: {symbol} {side} - {error_str}")
        return False, f"Hata: {error_str}"

def check_trailing_stop(current_price, pos_key, tp_level, side):
    """Trailing Stop kontrolü"""
    if tp_level != 2:
        return False, None, None
    
    max_prices = load_json(MAX_PRICE_FILE)
    max_price = max_prices.get(pos_key, current_price)
    
    if side == 'LONG':
        if current_price > max_price:
            max_price = current_price
            max_prices[pos_key] = max_price
            save_json(MAX_PRICE_FILE, max_prices)
    else:
        if current_price < max_price:
            max_price = current_price
            max_prices[pos_key] = max_price
            save_json(MAX_PRICE_FILE, max_prices)
    
    if side == 'LONG':
        if current_price < max_price * 0.985:
            logger.info(f"🎯 TRAILING STOP TETİKLENDİ: {pos_key} - Max: ${max_price:.4f} → Şimdi: ${current_price:.4f}")
            return True, f"📉 TRAILING! Max: ${max_price:.4f} → ${current_price:.4f}", max_price
    else:
        if current_price > max_price * 1.015:
            logger.info(f"🎯 TRAILING STOP TETİKLENDİ: {pos_key} - Min: ${max_price:.4f} → Şimdi: ${current_price:.4f}")
            return True, f"📈 TRAILING! Min: ${max_price:.4f} → ${current_price:.4f}", max_price
    
    return False, None, max_price

def check_tp_trigger(pnl_percent, tp_level, leverage):
    """TP tetikleme kontrolü"""
    rules = LEVERAGE_RULES.get(leverage, {})
    tp_type = rules.get('tp_type', 'standard')
    
    if tp_type == 'fast':
        if tp_level == 0 and pnl_percent >= 2:
            return 1, "💰 TP1 (FAST)! (%2 kar - %50 kapat)"
        if tp_level == 1 and pnl_percent >= 4:
            return 2, "💰 TP2 (FAST)! (%4 kar - kalan %50 kapat)"
    else:
        if tp_level == 0 and pnl_percent >= 3:
            return 1, "💰 TP1! (%3 kar - %50 kapat)"
        if tp_level == 1 and pnl_percent >= 5:
            return 2, "💰 TP2! (%5 kar - kalan %50 kapat)"
    
    return 0, None

def check_stop_loss(pnl_percent, leverage):
    """Stop Loss kontrolü"""
    rules = LEVERAGE_RULES.get(leverage)
    
    if not rules:
        return False, None
    
    stop_loss_percent = rules.get('stop_loss')
    
    if stop_loss_percent is None:
        return False, None
    
    if pnl_percent <= -stop_loss_percent:
        return True, f"🛑 STOP LOSS! ({stop_loss_percent}% düşüş)"
    
    return False, None

# DEFANS STRATEJİSİ — ROE EŞİKLERİ (4x kaldıraç):
#   D1 (ROE ≤ -20%):  coin -%5  → slot/5 (×0.20) USDT kontrat ekle (DCA)
#                      Binance entryPrice güncellenir, TP seviyeleri yeni ortalamaya göre
#   D2 (ROE ≤ -60%):  coin -%15 → sabit 25 USDT kontrat ekle (DCA)
#                      TP emirleri iptal edilir (tp_levels="BREAKEVEN")
#                      Hedef: fiyat yeni ortalamaya döndüğünde pozisyonu kapat
#   D3 (ROE ≤ -100%): coin -%25 → slot×0.30 USDT sadece margin ekle (kontrakt YOK)
#                      D2'deki break-even emri korunur
def check_defense_trigger(unrealized_pnl, initial_margin, defense_level, leverage):
    """Savunma tetikleme - ROE bazlı (unrealized_pnl / initial_margin * 100)"""
    rules = LEVERAGE_RULES.get(leverage)

    if not rules or not rules.get('defense_count'):
        return 0, None
    if initial_margin <= 0:
        return 0, None

    roe = (unrealized_pnl / initial_margin) * 100  # negatif = zarar

    if leverage == 4:
        # D1: coin -%5  → 4x kaldıraçta ROE -20%
        # D2: coin -%12 → 4x kaldıraçta ROE -48%
        # D3: coin -%25 → 4x kaldıraçta ROE -100%
        if defense_level == 0 and roe <= -20:
            return 1, f"🚨 SAVUNMA 1! (ROE {roe:.1f}%)"
        if defense_level == 1 and roe <= -48:
            return 2, f"🚨 SAVUNMA 2! (ROE {roe:.1f}%)"
        if defense_level == 2 and roe <= -100:
            return 3, f"🚨 SAVUNMA 3! (ROE {roe:.1f}%)"

    return 0, None

def check_d1_price_trigger(current_price: float, pos_key: str,
                            stop_levels: dict, side: str):
    """PDF stop seviyesine göre D1 tetikleme — ROE yetersiz olsa bile çalışır."""
    stop_px = stop_levels.get(pos_key)
    if stop_px is None:
        return False, None
    if side == 'LONG' and current_price <= stop_px:
        return True, f"🎯 D1 FİYAT TETİKLENDİ: ${current_price:.4f} ≤ Stop ${stop_px:.4f}"
    if side == 'SHORT' and current_price >= stop_px:
        return True, f"🎯 D1 FİYAT TETİKLENDİ: ${current_price:.4f} ≥ Stop ${stop_px:.4f}"
    return False, None

def cancel_stale_limit_orders(client, pending_orders: dict, stop_levels: dict) -> bool:
    """LIMIT_ORDER_TTL_H saatte dolmayan limit emirlerini iptal et.
    Değişiklik olduysa True döner (kaydetmek için)."""
    now     = time.time()
    changed = False
    stale   = [pk for pk, info in pending_orders.items()
               if (now - info.get('placed_at', now)) / 3600 >= LIMIT_ORDER_TTL_H]

    for pos_key in stale:
        info     = pending_orders[pos_key]
        symbol   = info['symbol']
        order_id = info['order_id']
        age_h    = (now - info['placed_at']) / 3600

        cancelled = False
        try:
            client.futures_cancel_order(symbol=symbol, orderId=order_id)
            cancelled = True
            logger.info(f"⏰ LİMİT İPTAL: {pos_key} — {age_h:.1f}h dolmadı, emir iptal edildi (#{order_id})")
        except Exception as e:
            err = str(e)
            if '-2011' in err:
                # Emir zaten dolmuş veya iptal edilmiş — stop_levels korunur
                logger.info(f"⚠️ LİMİT İPTAL: {pos_key} — emir #{order_id} zaten kapanmış (-2011), takip temizlendi")
            else:
                logger.error(f"❌ LİMİT İPTAL HATASI: {pos_key} — {err[:80]}")
            # Her durumda pending listesinden çıkar
            cancelled = True  # cleanup için

        if cancelled:
            pending_orders.pop(pos_key, None)
            stop_levels.pop(pos_key, None)
            changed = True
            send_notification(
                f"⏰ *LİMİT EMİR İPTAL — {pos_key.replace('_', ' ')}*\n"
                f"📌 {LIMIT_ORDER_TTL_H}h içinde dolmadı\n"
                f"🗑️ Slot serbest bırakıldı"
            )

    return changed


# Aynı engine oturumunda SLOT_LIMIT'e takılan (pos_key, defense_level) çiftleri
_slot_limit_blocked = set()

LOCK_FILE = "engine.lock"

def acquire_lock():
    """Tek instance garantisi — PID lock dosyası."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                logger.error(f"❌ ENGINE ZATEN ÇALIŞIYOR! PID={old_pid}. Çıkılıyor.")
                return False
        except Exception:
            pass  # Eski/bozuk lock — üzerine yaz
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

def main():
    if not acquire_lock():
        return

    logger.info("=" * 70)
    logger.info("🚀 MİNA v2 - EXECUTION ENGINE BAŞLATILDI (LOGGING AKTİF)")
    logger.info("=" * 70)
    logger.info(f"📊 Kaldıraçlar: 1x, 2x, 3x, 4x⭐, 5x, 10x")
    logger.info(f"🛑 Stop Loss: 1x=%2, 2x=%3, 3x=%2, 4x=YOK, 5x=%2, 10x=%1")
    logger.info(f"💰 TP: Standard 1-5x (TP1:%3 TP2:%5+Trailing) | 10x (TP1:%2 TP2:%4 tam kapat)")
    logger.info(f"🛡️  Savunma: 2x(0), 4x(3)⭐, 5x(0), 10x(0)")
    logger.info(f"🎯 Trailing: TP2 sonrası %1.5")
    logger.info(f"📝 Log Dosyası: mina_bot.log")
    logger.info("=" * 70)

    send_notification(
        f"🚀 *MİNA v2 ENGINE BAŞLADI*\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"⚙️ Check interval: {30}s\n"
        f"✅ Sistem aktif!"
    )

    config = BinanceConfig()
    client = config.get_client()
    
    defense_levels  = load_json(DEFENSE_FILE)
    tp_levels       = load_json(TP_FILE)
    initial_margins = load_json(INITIAL_MARGIN_FILE)
    stop_levels     = load_json(STOP_LEVELS_FILE)
    pending_orders  = load_json(PENDING_ORDERS_FILE)
    tp_stop_orders  = load_json(TP_STOP_FILE)
    initial_qtys    = load_json(INITIAL_QTY_FILE)
    d2_be_orders    = load_json(D2_BE_FILE)
    
    last_message_time = 0
    check_interval = 60
    
    while True:
        try:
            positions = get_open_positions(client)

            # ── 48h dolmayan limit emirleri iptal et ─────────────────────────
            if cancel_stale_limit_orders(client, pending_orders, stop_levels):
                save_json(PENDING_ORDERS_FILE, pending_orders)
                save_json(STOP_LEVELS_FILE, stop_levels)
            # ─────────────────────────────────────────────────────────────────

            # ── Reconciliation: harici kapanma / likidasyonu tespit et ──────
            binance_keys = {
                f"{p['symbol']}_{'LONG' if float(p['positionAmt']) > 0 else 'SHORT'}"
                for p in positions
            }
            all_tracked = set(defense_levels) | set(initial_margins) | set(tp_levels) | set(initial_qtys) | set(d2_be_orders)
            orphaned    = all_tracked - binance_keys

            if orphaned:
                max_prices = load_json(MAX_PRICE_FILE)
                for pos_key in orphaned:
                    cancel_tp1_stop_order(client, pos_key, tp_stop_orders)
                    cancel_d2_be_order(client, pos_key, d2_be_orders)
                    for _d in [defense_levels, initial_margins, tp_levels, initial_qtys]:
                        _d.pop(pos_key, None)
                    max_prices.pop(pos_key, None)
                    stop_levels.pop(pos_key, None)
                    logger.info(f"🔄 MUTABAKAT: {pos_key} Binance'te yok — takipten silindi")
                    send_notification(
                        f"⚡ *HARICI KAPANMA — {pos_key.replace('_', ' ')}*\n"
                        f"📌 Binance'te pozisyon bulunamadı\n"
                        f"🗑️ Takip verisi temizlendi"
                    )
                save_json(DEFENSE_FILE, defense_levels)
                save_json(INITIAL_MARGIN_FILE, initial_margins)
                save_json(INITIAL_QTY_FILE, initial_qtys)
                save_json(TP_FILE, tp_levels)
                save_json(MAX_PRICE_FILE, max_prices)
                save_json(STOP_LEVELS_FILE, stop_levels)
                save_json(TP_STOP_FILE, tp_stop_orders)
                save_json(D2_BE_FILE, d2_be_orders)
            # ─────────────────────────────────────────────────────────────────

            if len(positions) == 0:
                current_time = time.time()
                if current_time - last_message_time > 30:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📭 Açık pozisyon yok.")
                    last_message_time = current_time
            else:
                print(f"\n{'='*70}")
                print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - {len(positions)} Pozisyon")
                print(f"{'='*70}")
                
                for pos in positions:
                    symbol = pos['symbol']
                    side = 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
                    entry_price = float(pos['entryPrice'])
                    amount = abs(float(pos['positionAmt']))
                    leverage = int(pos['leverage'])
                    unrealized_pnl = float(pos['unRealizedProfit'])
                    liquidation_price = float(pos.get('liquidationPrice', 0))
                    iso_margin = float(pos.get('isolatedMargin', 0))

                    ticker = client.futures_symbol_ticker(symbol=symbol)
                    current_price = float(ticker['price'])
                    
                    pnl_percent = calculate_pnl_percent(entry_price, current_price, side)

                    pos_key = f"{symbol}_{side}"
                    current_defense = defense_levels.get(pos_key, 0)
                    current_tp = tp_levels.get(pos_key, 0)

                    # Initial margin ve orijinal qty takibi — ilk görüldüğünde kaydet
                    if pos_key not in initial_margins:
                        initial_margins[pos_key] = round((entry_price * amount) / leverage, 4)
                        initial_qtys[pos_key]    = amount
                        save_json(INITIAL_MARGIN_FILE, initial_margins)
                        save_json(INITIAL_QTY_FILE, initial_qtys)
                        # Limit emir doldu: pending takibinden çıkar
                        if pos_key in pending_orders:
                            pending_orders.pop(pos_key, None)
                            save_json(PENDING_ORDERS_FILE, pending_orders)
                        _icon = "🟢" if side == 'LONG' else "🔴"
                        send_notification(
                            f"{_icon} *POZİSYON TESPİT EDİLDİ*\n"
                            f"📌 {symbol} {side} {leverage}x\n"
                            f"💰 Giriş: ${entry_price:.4f} | Marj: ${iso_margin:.2f}\n"
                            f"🔴 Likidasyon: ${liquidation_price:.4f}"
                        )

                    init_margin = initial_margins[pos_key]
                    roe = (unrealized_pnl / init_margin) * 100 if init_margin > 0 else 0.0

                    rules = LEVERAGE_RULES.get(leverage, {})
                    tp_type = "FAST" if rules.get('tp_type') == 'fast' else "STD"

                    pnl_icon = "📈" if unrealized_pnl > 0 else "📉"
                    side_icon = "🟢" if side == 'LONG' else "🔴"

                    max_def = rules.get('defense_count', 0)

                    print(f"\n{side_icon} {symbol} - {side} {leverage}x ({tp_type})")
                    print(f"   💰 Giriş: ${entry_price:.4f}")
                    print(f"   📊 Şimdi: ${current_price:.4f}")
                    print(f"   📦 Miktar: {amount}")
                    print(f"   {pnl_icon} PnL: {pnl_percent:+.2f}% | ROE: {roe:+.2f}% (${unrealized_pnl:+.2f})")
                    print(f"   🛡️  Savunma: {current_defense}/{max_def} | Margin: ${init_margin:.2f}")
                    
                    # Stop Loss
                    sl_trigger, sl_msg = check_stop_loss(pnl_percent, leverage)
                    if sl_trigger:
                        print(f"\n   {sl_msg}")
                        print(f"   ⚡ Stop Loss emri gönderiliyor...")

                        success, message = send_stop_loss_order(client, symbol, side, amount)

                        if success or message == "POSITION_CLOSED":
                            if message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                            else:
                                print(f"   ✅ {message}")
                                send_notification(
                                    f"🛑 *STOP LOSS — {symbol} {side}*\n"
                                    f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                    f"💰 Giriş: ${entry_price:.4f}\n"
                                    f"📊 Fiyat: ${current_price:.4f}\n"
                                    f"📉 Zarar: ${unrealized_pnl:+.2f}\n"
                                    f"✅ Pozisyon kapatıldı"
                                )
                            if pos_key in tp_levels:
                                del tp_levels[pos_key]
                            if pos_key in defense_levels:
                                del defense_levels[pos_key]
                            if pos_key in initial_margins:
                                del initial_margins[pos_key]
                            initial_qtys.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)
                            cancel_d2_be_order(client, pos_key, d2_be_orders)
                            save_json(TP_STOP_FILE, tp_stop_orders)
                            save_json(D2_BE_FILE, d2_be_orders)
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(INITIAL_QTY_FILE, initial_qtys)
                            save_json(MAX_PRICE_FILE, max_prices)
                        else:
                            print(f"   ❌ {message}")
                        continue

                    # Trailing Stop
                    trailing_trigger, trailing_msg, max_price = check_trailing_stop(
                        current_price, pos_key, current_tp, side
                    )
                    
                    if current_tp == 2 and max_price:
                        print(f"   🎯 Trailing - Max: ${max_price:.4f}")
                    
                    if trailing_trigger:
                        print(f"\n   {trailing_msg}")
                        print(f"   ⚡ Trailing emri gönderiliyor...")

                        success, message = send_tp_order(client, symbol, side, amount, 3)

                        if success or message == "POSITION_CLOSED":
                            if message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                            else:
                                print(f"   ✅ {message}")
                                send_notification(
                                    f"🎯 *TRAİLİNG STOP — {symbol} {side}*\n"
                                    f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                    f"💰 Giriş: ${entry_price:.4f}\n"
                                    f"📊 Fiyat: ${current_price:.4f}\n"
                                    f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                    f"✅ Tüm pozisyon kapatıldı"
                                )
                            if pos_key in tp_levels:
                                del tp_levels[pos_key]
                            if pos_key in defense_levels:
                                del defense_levels[pos_key]
                            if pos_key in initial_margins:
                                del initial_margins[pos_key]
                            initial_qtys.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)
                            cancel_d2_be_order(client, pos_key, d2_be_orders)
                            save_json(TP_STOP_FILE, tp_stop_orders)
                            save_json(D2_BE_FILE, d2_be_orders)
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(INITIAL_QTY_FILE, initial_qtys)
                            save_json(MAX_PRICE_FILE, max_prices)
                        else:
                            print(f"   ❌ {message}")
                        continue

                    # TP
                    if pnl_percent > 0:
                        tp_trigger, tp_msg = check_tp_trigger(pnl_percent, current_tp, leverage)

                        if tp_trigger:
                            print(f"\n   {tp_msg}")
                            print(f"   ⚡ TP emri gönderiliyor...")

                            # Orijinal giris miktari: ilk açılıştaki positionAmt (D1 DCA'dan bağımsız)
                            prec     = get_symbol_precision(client, symbol)
                            init_qty = round(initial_qtys.get(pos_key, amount), prec)
                            lev_rules = LEVERAGE_RULES.get(leverage, {})
                            tp_type   = lev_rules.get('tp_type', 'standard')

                            success, message = send_tp_order(client, symbol, side, amount, tp_trigger,
                                                             initial_amount=init_qty, tp_type=tp_type)

                            if success:
                                print(f"   ✅ {message}")
                                if tp_trigger == 2 and tp_type == 'fast':
                                    # 10x TP2: tum pozisyon kapandi, temizle
                                    send_notification(
                                        f"💰 *KÂR AL 2 (10x) — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ Tüm pozisyon kapatıldı (Trailing yok)"
                                    )
                                    cancel_tp1_stop_order(client, pos_key, tp_stop_orders)
                                    cancel_d2_be_order(client, pos_key, d2_be_orders)
                                    for _d in [tp_levels, defense_levels, initial_margins, initial_qtys]:
                                        _d.pop(pos_key, None)
                                    max_prices = load_json(MAX_PRICE_FILE)
                                    max_prices.pop(pos_key, None)
                                    save_json(TP_STOP_FILE, tp_stop_orders)
                                    save_json(D2_BE_FILE, d2_be_orders)
                                    save_json(TP_FILE, tp_levels)
                                    save_json(DEFENSE_FILE, defense_levels)
                                    save_json(INITIAL_MARGIN_FILE, initial_margins)
                                    save_json(INITIAL_QTY_FILE, initial_qtys)
                                    save_json(MAX_PRICE_FILE, max_prices)
                                elif tp_trigger == 2:
                                    # Standard TP2: %50 kapandi, trailing baslar
                                    tp_levels[pos_key] = tp_trigger
                                    save_json(TP_FILE, tp_levels)
                                    send_notification(
                                        f"💰 *KÂR AL 2 — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ %50 kapatıldı\n🎯 Trailing aktif!"
                                    )
                                    max_prices = load_json(MAX_PRICE_FILE)
                                    max_prices[pos_key] = current_price
                                    save_json(MAX_PRICE_FILE, max_prices)
                                    print(f"   Trailing aktif! Başlangıç: ${current_price:.4f}")
                                else:
                                    # TP1: %50 kapandi, stop order gonder
                                    tp_levels[pos_key] = tp_trigger
                                    save_json(TP_FILE, tp_levels)
                                    send_notification(
                                        f"💰 *KÂR AL 1 — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ %50 kapatıldı (orijinal giriş)\n🛡️ Stop giriş fiyatına çekildi"
                                    )
                                    max_prices = load_json(MAX_PRICE_FILE)
                                    max_prices[pos_key] = current_price
                                    save_json(MAX_PRICE_FILE, max_prices)
                                    remaining = round(init_qty * 0.50, prec)
                                    ok, stop_id = send_tp1_stop_order(
                                        client, symbol, side, entry_price, remaining
                                    )
                                    if ok:
                                        tp_stop_orders[pos_key] = {
                                            'symbol':     symbol,
                                            'order_id':   stop_id,
                                            'stop_price': entry_price,
                                        }
                                        save_json(TP_STOP_FILE, tp_stop_orders)
                                        print(f"   Stop order gonderildi: stopPrice={entry_price:.6f} qty={remaining} orderId={stop_id}")
                                    else:
                                        print(f"   Stop order gonderilemedi!")
                            elif message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                                if pos_key in tp_levels:
                                    del tp_levels[pos_key]
                                if pos_key in defense_levels:
                                    del defense_levels[pos_key]
                                if pos_key in initial_margins:
                                    del initial_margins[pos_key]
                                initial_qtys.pop(pos_key, None)
                                max_prices = load_json(MAX_PRICE_FILE)
                                if pos_key in max_prices:
                                    del max_prices[pos_key]
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(INITIAL_QTY_FILE, initial_qtys)
                                save_json(MAX_PRICE_FILE, max_prices)
                            elif message == "HEDGE_NOT_SUPPORTED":
                                if pos_key in tp_levels:
                                    del tp_levels[pos_key]
                                if pos_key in initial_margins:
                                    del initial_margins[pos_key]
                                if pos_key in defense_levels:
                                    del defense_levels[pos_key]
                                initial_qtys.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(INITIAL_QTY_FILE, initial_qtys)
                                save_json(DEFENSE_FILE, defense_levels)
                                print(f"   ⚠️ {symbol} {side} takipten çıkarıldı (hedge mode kısıtı)")
                            else:
                                print(f"   ❌ {message}")
                    
                    # Başabaş kapama (TP1 sonrası fiyat geri döndüyse)
                    # D3 sonrası başabaş kapama
                    # D3 break-even: ROE >= -2% olduğunda kapatılır.
                    # Tam 0% değil — komisyon + slippage için -%2 emniyet payı.
                    # 4x kaldıraçta coin fiyatında sadece %0.5 fark eder.
                    if current_defense == 3 and roe >= -2:
                        logger.info(f"🛡️  D3 BAŞABAŞ: {symbol} {side} ROE {roe:+.1f}% → kapatılıyor")
                        print(f"\n   🛡️  D3 BAŞABAŞ! ROE {roe:+.1f}% — pozisyon kapatılıyor...")
                        success, message = send_stop_loss_order(client, symbol, side, amount)
                        if success or message == "POSITION_CLOSED":
                            if message != "POSITION_CLOSED":
                                send_notification(
                                    f"🛡️ *D3 BAŞABAŞ — {symbol} {side}*\n"
                                    f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                    f"💰 Giriş: ${entry_price:.4f}\n"
                                    f"📊 Fiyat: ${current_price:.4f}\n"
                                    f"✅ Pozisyon kapatıldı"
                                )
                            for _d in [tp_levels, defense_levels, initial_margins, initial_qtys]:
                                _d.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            max_prices.pop(pos_key, None)
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(INITIAL_QTY_FILE, initial_qtys)
                            save_json(MAX_PRICE_FILE, max_prices)
                        else:
                            print(f"   ❌ {message}")
                        continue

                    # D2 sonrası break-even (Binance TAKE_PROFIT_MARKET order bekliyor)
                    if current_tp == "BREAKEVEN":
                        if pos_key in d2_be_orders:
                            be_info = d2_be_orders[pos_key]
                            print(f"   ⏳ D2 BE bekliyor: stopPrice=${be_info.get('stop_price', 0):.6f} orderId={be_info.get('order_id', '?')}")
                        else:
                            be_price = entry_price * (1.0012 if side == 'LONG' else 0.9988)
                            ok_be, be_id = send_d2_be_order(client, symbol, side, amount, be_price)
                            if ok_be:
                                d2_be_orders[pos_key] = {
                                    'symbol':     symbol,
                                    'order_id':   be_id,
                                    'stop_price': be_price,
                                }
                                save_json(D2_BE_FILE, d2_be_orders)
                                print(f"   ✅ D2 BE order yeniden gönderildi: stopPrice=${be_price:.6f}")
                            else:
                                print(f"   ❌ D2 BE order gönderilemedi!")
                        continue

                    # Savunma — aynı döngüde zincirleme tetikleme (BUG5)
                    while True:
                        defense_trigger, defense_msg = check_defense_trigger(
                            unrealized_pnl, init_margin, current_defense, leverage
                        )
                        # ROE tetiklemediyse PDF stop seviyesi bazlı D1 kontrolü
                        if not defense_trigger and current_defense == 0:
                            price_d1, price_msg = check_d1_price_trigger(
                                current_price, pos_key, stop_levels, side
                            )
                            if price_d1:
                                defense_trigger = 1
                                defense_msg     = price_msg
                        if not defense_trigger:
                            break
                        if (pos_key, defense_trigger) in _slot_limit_blocked:
                            break

                        print(f"\n   {defense_msg}")
                        print(f"   ⚡ Savunma emri gönderiliyor...")

                        success, message = send_defense_order(
                            client, symbol, side, defense_trigger, leverage
                        )

                        if success:
                            print(f"   ✅ {message}")
                            current_defense = defense_trigger
                            defense_levels[pos_key] = current_defense
                            save_json(DEFENSE_FILE, defense_levels)
                            # D1 tetiklendi: stop seviyesi artık gereksiz
                            if defense_trigger == 1 and pos_key in stop_levels:
                                stop_levels.pop(pos_key, None)
                                save_json(STOP_LEVELS_FILE, stop_levels)
                            # D2: mevcut TP emirlerini iptal et, break-even moduna geç
                            if defense_trigger == 2:
                                tp_levels[pos_key] = "BREAKEVEN"
                                save_json(TP_FILE, tp_levels)
                                current_tp = "BREAKEVEN"
                                logger.info(f"🔄 D2 SONRASI: {symbol} {side} TP iptal, break-even modu aktif")
                            try:
                                upd = client.futures_position_information(symbol=symbol)
                                _p  = next((p for p in upd
                                    if p['symbol'] == symbol and float(p['positionAmt']) != 0
                                    and (float(p['positionAmt']) > 0) == (side == 'LONG')), None)
                                new_liq   = float(_p['liquidationPrice']) if _p else 0
                                new_mrg   = float(_p['isolatedMargin'])   if _p else 0
                                new_entry = float(_p['entryPrice'])        if _p else entry_price
                                new_qty   = abs(float(_p['positionAmt'])) if _p else amount
                            except Exception:
                                new_liq, new_mrg   = 0, 0
                                new_entry, new_qty = entry_price, amount
                            # BUG3: init_margin'i Binance'ten gelen gerçek marjla güncelle
                            if new_mrg > 0:
                                init_margin = new_mrg
                                initial_margins[pos_key] = round(new_mrg, 4)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                            if defense_trigger == 2:
                                be_price = new_entry * (1.0012 if side == 'LONG' else 0.9988)
                                ok_be, be_id = send_d2_be_order(client, symbol, side, new_qty, be_price)
                                if ok_be:
                                    d2_be_orders[pos_key] = {
                                        'symbol':     symbol,
                                        'order_id':   be_id,
                                        'stop_price': be_price,
                                    }
                                    save_json(D2_BE_FILE, d2_be_orders)
                                    print(f"   ✅ D2 BE order gönderildi: stopPrice=${be_price:.6f}")
                                else:
                                    print(f"   ❌ D2 BE order gönderilemedi!")
                            liq_line = (
                                f"🔴 Eski likidasyon: ${liquidation_price:.4f}\n"
                                f"🔴 Yeni likidasyon: ~${new_liq:.4f}"
                            ) if new_liq > 0 else f"🔴 Likidasyon: ${liquidation_price:.4f}"
                            send_notification(
                                f"🛡️ *SAVUNMA {defense_trigger} — {symbol} {side}*\n"
                                f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                f"💰 Giriş: ${entry_price:.4f} | Fiyat: ${current_price:.4f}\n"
                                f"➕ {message} | Yeni marj: ${new_mrg:.2f}\n"
                                f"{liq_line}"
                            )
                        elif message == "POSITION_CLOSED":
                            print(f"   ⚠️ Pozisyon zaten kapalı, savunma atlandı: {symbol} {side}")
                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)
                            cancel_d2_be_order(client, pos_key, d2_be_orders)
                            for _d in [defense_levels, initial_margins, tp_levels, initial_qtys]:
                                _d.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            max_prices.pop(pos_key, None)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(INITIAL_QTY_FILE, initial_qtys)
                            save_json(TP_FILE, tp_levels)
                            save_json(MAX_PRICE_FILE, max_prices)
                            save_json(TP_STOP_FILE, tp_stop_orders)
                            save_json(D2_BE_FILE, d2_be_orders)
                            break
                        elif message == "MARGIN_FAILED":
                            print(f"   ❌ D{defense_trigger} margin eklenemedi, bir sonraki döngüde tekrar denenecek: {symbol} {side}")
                            break
                        elif message == "SLOT_LIMIT":
                            _slot_limit_blocked.add((pos_key, defense_trigger))
                            logger.warning(f"⛔ SLOT LİMİTİ: {symbol} {side} D{defense_trigger} iptal — bu oturumda tekrar denenmeyecek.")
                            break
                        else:
                            print(f"   ❌ {message}")
                            break
                
                print(f"{'='*70}\n")
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 Engine kullanıcı tarafından durduruldu")
            send_notification(
                f"🛑 *MİNA v2 ENGINE DURDURULDU*\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            break
        except Exception as e:
            err_str = str(e)
            logger.error(f"❌ KRİTİK HATA: {err_str}")
            logger.error(traceback.format_exc())

            if 'banned until' in err_str:
                match = re.search(r'banned until (\d+)', err_str)
                if match:
                    ban_until = int(match.group(1)) / 1000
                    wait = max(0, ban_until - time.time()) + 5
                    logger.warning(f"⛔ IP BAN! {int(wait):.0f} saniye bekleniyor (ban bitişine kadar)...")
                    time.sleep(wait)
                else:
                    logger.warning("⛔ IP BAN (timestamp yok)! 120 saniye bekleniyor...")
                    time.sleep(120)
            elif '-1003' in err_str or 'Too many requests' in err_str:
                logger.warning("⚠️ RATE LİMİT! 60 saniye bekleniyor...")
                time.sleep(60)
            elif 'Connection' in err_str or 'ConnectionError' in err_str:
                logger.warning("🔌 Bağlantı hatası, 15 saniye sonra tekrar denenecek...")
                time.sleep(15)
            else:
                time.sleep(check_interval)

    release_lock()

if __name__ == "__main__":
    main()