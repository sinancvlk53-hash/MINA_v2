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
logger.propagate = False  # root logger'a taşıma — çiftlenme önlenir

if not logger.handlers:
    # Dosyaya yazma — systemd StandardOutput=append:mina_bot.log ile çakışmasın
    # diye console_handler yok; file_handler tek kayıt noktası
    file_handler = logging.FileHandler('mina_bot.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(file_handler)

# ═══════════════════════════════════════════════

# Tracking dosyaları
DEFENSE_FILE        = "defense_levels.json"
TP_FILE             = "tp_levels.json"
MAX_PRICE_FILE      = "max_prices.json"
INITIAL_MARGIN_FILE = "initial_margins.json"
STOP_LEVELS_FILE    = "stop_levels.json"
PENDING_ORDERS_FILE = "pending_orders.json"
INITIAL_PRICE_FILE  = "initial_entry_prices.json"
DEFENSE_STOPS_FILE  = "defense_stop_orders.json"
LIMIT_ORDER_TTL_H   = 48

# Özel kaldıraç kuralları
LEVERAGE_RULES = {
    # tp1_pct       : TP1 tetik eşiği (%)
    # tp2_pct       : TP2 tetik eşiği (%)
    # tp2_close     : TP2'de kapatılacak oran (current_amount'a göre)
    # trailing_callback : TRAILING_STOP_MARKET callbackRate (%), None = trailing yok
    1:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    2:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    3:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    4:  {'stop_loss': None, 'defense_count': 3, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    5:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    6:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    7:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    8:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    9:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    10: {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'fast',     'tp1_pct': 2, 'tp2_pct': 4, 'tp2_close': 1.00, 'trailing_callback': None},
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
_price_precision_cache = {}

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

def get_price_precision(client, symbol):
    """Sembol için fiyat precision'ını cache'li getir (PRICE_FILTER tickSize)"""
    if symbol in _price_precision_cache:
        return _price_precision_cache[symbol]
    exchange_info = client.futures_exchange_info()
    import math as _math
    for s in exchange_info['symbols']:
        sym = s['symbol']
        for f in s['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                tick = float(f['tickSize'])
                # str(tick) bilimsel notasyona düşebilir (örn. 1e-06) — log10 kullan
                if tick >= 1:
                    prec = 0
                elif tick > 0:
                    prec = max(0, -int(_math.floor(_math.log10(tick))))
                else:
                    prec = 8
                _price_precision_cache[sym] = prec
                break
    return _price_precision_cache.get(symbol, 2)

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

# KAR ALMA STRATEJİSİ — 1x–9x (standard):
#   TP1 (+3%): current_amount'un %50'si kapatılır. Stop-loss giriş fiyatına çekilir.
#   TP2 (+5%): O anki pozisyonun %50'si kapatılır (= başlangıç pozisyonunun %25'i).
#              Aynı anda TRAILING_STOP_MARKET: activationPrice=TP2 fiyatı, callbackRate=%2.
#   Trailing : Binance-native TRAILING_STOP_MARKET. Fiyat tepeden -%2 düşünce kalan %25 kapanır.
# KAR ALMA STRATEJİSİ — 10x (fast):
#   TP1 (+2%): current_amount'un %50'si kapatılır. Stop-loss giriş fiyatına çekilir.
#   TP2 (+4%): Kalan pozisyonun %100'ü kapatılır. Trailing YOK.
#   Bileşik  : Pozisyon kapanınca realized kar bakiyeye işlenir; sonraki slot
#              get_usdt_balance() ile taze bakiye üzerinden otomatik hesaplanır.
def send_tp_order(client, symbol, side, current_amount, tp_level, tp_type='standard'):
    """Take Profit emri gönder"""
    try:
        if tp_level == 1:
            close_percent = 0.50
        elif tp_level == 2:
            close_percent = 0.50 if tp_type == 'standard' else 1.00
        elif tp_level == 3:
            close_percent = 1.00
        else:
            return False, "Geçersiz TP level"
        
        close_amount = current_amount * close_percent
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

def send_trailing_stop_order(client, symbol, side, quantity, activation_price, callback_rate=2.0):
    """TP2 sonrası TRAILING_STOP_MARKET emri gönder (1x-9x standard)"""
    try:
        order_side   = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pos_side_str = 'LONG' if side == 'LONG' else 'SHORT'
        price_prec   = get_price_precision(client, symbol)
        act_price    = round(activation_price, price_prec)

        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type='TRAILING_STOP_MARKET',
            quantity=quantity,
            activationPrice=act_price,
            callbackRate=callback_rate,
            positionSide=pos_side_str,
            workingType='MARK_PRICE',
        )
        order_id = order['orderId']
        logger.info(f"🎯 TRAILING_STOP_MARKET: {symbol} {side} qty={quantity} activationPrice=${act_price} callbackRate={callback_rate}% orderId={order_id}")
        return True, order_id
    except Exception as e:
        logger.error(f"❌ TRAILING_STOP_MARKET HATASI: {symbol} {side} - {e}")
        return False, None


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
                1: slot_size * 0.20,  # D1: slot'un %20'si (DCA kontrat)
                2: slot_size * 0.20,  # D2: slot'un %20'si (DCA kontrat) + STOP_MARKET başabaş
                3: slot_size * 0.40   # D3: slot'un %40'ı (DCA kontrat) + yeni STOP_MARKET
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

        # D1/D2/D3 — kontrakt ekle
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
    rules   = LEVERAGE_RULES.get(leverage, {})
    tp1_pct = rules.get('tp1_pct', 3)
    tp2_pct = rules.get('tp2_pct', 5)
    tp_type = rules.get('tp_type', 'standard')

    tag = "(FAST) " if tp_type == 'fast' else ""
    if tp_level == 0 and pnl_percent >= tp1_pct:
        return 1, f"💰 TP1 {tag}(%{tp1_pct} kar - %50 kapat)"
    if tp_level == 1 and pnl_percent >= tp2_pct:
        close_lbl = "%100 kapat" if tp_type == 'fast' else "%25 kapat + Trailing"
        return 2, f"💰 TP2 {tag}(%{tp2_pct} kar - {close_lbl})"

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

# DEFANS STRATEJİSİ — TETİKLEME EŞİKLERİ (4x kaldıraç):
#   D1 (ROE ≤ -20%):  coin -%5  → slot×0.20 USDT kontrat ekle (DCA)
#                      Binance entryPrice güncellenir, TP seviyeleri yeni ortalamaya göre
#   D2 (FİYAT -%12):  initial_entry_price * 0.88 → slot×0.20 kontrat ekle (DCA)
#                      TP emirleri iptal edilir (tp_levels="BREAKEVEN")
#                      Binance'e TAKE_PROFIT_MARKET: entry_price * 0.9434 * 1.0012
#   D3 (FİYAT -%25):  initial_entry_price * 0.75 → slot×0.40 kontrat ekle (DCA)
#                      D2 stop iptal, yeni TAKE_PROFIT_MARKET: entry_price * 0.8817 * 1.0012
#                      BREAKEVEN modu kalkar, normal TP devreye girer
def check_defense_trigger(unrealized_pnl, initial_margin, defense_level, leverage):
    """Savunma tetikleme - ROE bazlı (unrealized_pnl / initial_margin * 100)
    D2/D3 fiyat bazlı — check_d2_price_trigger / check_d3_price_trigger ile kontrol edilir."""
    rules = LEVERAGE_RULES.get(leverage)

    if not rules or not rules.get('defense_count'):
        return 0, None
    if initial_margin <= 0:
        return 0, None

    roe = (unrealized_pnl / initial_margin) * 100  # negatif = zarar

    if leverage == 4:
        # D1: coin -%5  → 4x kaldıraçta ROE -20%
        # D2: fiyat bazlı → check_d2_price_trigger ile tetiklenir
        # D3: fiyat bazlı → check_d3_price_trigger ile tetiklenir
        if defense_level == 0 and roe <= -20:
            return 1, f"🚨 SAVUNMA 1! (ROE {roe:.1f}%)"

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

def check_d2_price_trigger(current_price: float, pos_key: str,
                            initial_entry_prices: dict, side: str):
    """D2 fiyat bazlı tetikleme — initial_entry_price * 0.88 (giriş -%12)"""
    initial_ep = initial_entry_prices.get(pos_key)
    if initial_ep is None:
        return False, None
    if side == 'LONG':
        trigger_px = initial_ep * 0.88
        if current_price <= trigger_px:
            return True, f"🚨 SAVUNMA 2! D2 FİYAT: ${current_price:.4f} ≤ ${trigger_px:.4f} (giriş -%12)"
    else:
        trigger_px = initial_ep * 1.12
        if current_price >= trigger_px:
            return True, f"🚨 SAVUNMA 2! D2 FİYAT: ${current_price:.4f} ≥ ${trigger_px:.4f} (giriş +%12)"
    return False, None

def check_d3_price_trigger(current_price: float, pos_key: str,
                            initial_entry_prices: dict, side: str):
    """D3 fiyat bazlı tetikleme — initial_entry_price * 0.75 (giriş -%25)"""
    initial_ep = initial_entry_prices.get(pos_key)
    if initial_ep is None:
        return False, None
    if side == 'LONG':
        trigger_px = initial_ep * 0.75
        if current_price <= trigger_px:
            return True, f"🚨 SAVUNMA 3! D3 FİYAT: ${current_price:.4f} ≤ ${trigger_px:.4f} (giriş -%25)"
    else:
        trigger_px = initial_ep * 1.25
        if current_price >= trigger_px:
            return True, f"🚨 SAVUNMA 3! D3 FİYAT: ${current_price:.4f} ≥ ${trigger_px:.4f} (giriş +%25)"
    return False, None

def send_stop_market_defense(client, symbol, side, stop_price, label="DEFENSE STOP"):
    """D2/D3 başabaş emri: önce TAKE_PROFIT_MARKET (mainnet), -4120 hatasında LIMIT GTC (testnet fallback).
    Fiyat stop_price seviyesine ulaştığında pozisyon kapanır."""
    try:
        order_side   = SIDE_SELL if side == 'LONG' else SIDE_BUY
        pos_side_str = 'LONG'   if side == 'LONG' else 'SHORT'
        price_prec   = get_price_precision(client, symbol)
        stop_rounded = round(stop_price, price_prec)

        # Pozisyon miktarını al
        pos_info = client.futures_position_information(symbol=symbol)
        qty = 0.0
        for p in pos_info:
            p_amt  = float(p.get('positionAmt', 0))
            p_side = p.get('positionSide', '')
            if p['symbol'] == symbol and p_side == pos_side_str and p_amt != 0:
                qty = abs(p_amt)
                break

        if qty == 0:
            logger.warning(f"⚠️ {label}: {symbol} {side} pozisyon bulunamadı (qty=0) — atlanıyor")
            return None

        sym_prec = get_symbol_precision(client, symbol)
        qty      = round(qty, sym_prec)

        # 1. TAKE_PROFIT_MARKET dene (mainnet)
        try:
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type='TAKE_PROFIT_MARKET',
                stopPrice=stop_rounded,
                positionSide=pos_side_str,
                quantity=qty,
                workingType='MARK_PRICE',
            )
            order_type = 'TAKE_PROFIT_MARKET'
        except Exception as e1:
            if '-4120' not in str(e1):
                raise
            # -4120: Algo endpoint gerekiyor — LIMIT GTC fallback (testnet uyumlu)
            logger.warning(f"⚠️ {label}: TAKE_PROFIT_MARKET -4120 → LIMIT GTC fallback ({symbol} {side})")
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type='LIMIT',
                price=stop_rounded,
                timeInForce='GTC',
                positionSide=pos_side_str,
                quantity=qty,
            )
            order_type = 'LIMIT'

        order_id = order['orderId']
        logger.info(f"✅ {label}: {symbol} {side} {order_type} qty={qty} stop/price=${stop_rounded} orderId={order_id}")
        return order_id
    except Exception as e:
        logger.error(f"❌ {label} STOP EMRİ HATASI: {symbol} {side} - {e}")
        return None

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
    logger.info(f"💰 TP 1x-9x: TP1@%3→%50 kapat | TP2@%5→%25 kapat + TRAILING_STOP_MARKET callback%2")
    logger.info(f"💰 TP 10x  : TP1@%2→%50 kapat | TP2@%4→%100 kapat | Trailing YOK")
    logger.info(f"🛡️  Savunma: 2x(0), 4x(3)⭐, 5x(0), 10x(0)")
    logger.info(f"🎯 Trailing: Binance-native TRAILING_STOP_MARKET, callbackRate=%2 (1x-9x)")
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
    
    defense_levels       = load_json(DEFENSE_FILE)
    tp_levels            = load_json(TP_FILE)
    initial_margins      = load_json(INITIAL_MARGIN_FILE)
    stop_levels          = load_json(STOP_LEVELS_FILE)
    pending_orders       = load_json(PENDING_ORDERS_FILE)
    initial_entry_prices = load_json(INITIAL_PRICE_FILE)
    defense_stops        = load_json(DEFENSE_STOPS_FILE)
    
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
            all_tracked = set(defense_levels) | set(initial_margins) | set(tp_levels)
            orphaned    = all_tracked - binance_keys

            if orphaned:
                max_prices = load_json(MAX_PRICE_FILE)
                for pos_key in orphaned:
                    for _d in [defense_levels, initial_margins, tp_levels,
                                initial_entry_prices, defense_stops]:
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
                save_json(TP_FILE, tp_levels)
                save_json(MAX_PRICE_FILE, max_prices)
                save_json(STOP_LEVELS_FILE, stop_levels)
                save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                save_json(DEFENSE_STOPS_FILE, defense_stops)
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

                    # Initial margin takibi — ilk görüldüğünde kaydet
                    if pos_key not in initial_margins:
                        initial_margins[pos_key] = round((entry_price * amount) / leverage, 4)
                        save_json(INITIAL_MARGIN_FILE, initial_margins)
                        # İlk giriş fiyatını kaydet (D2 fiyat tetiklemesi için)
                        if pos_key not in initial_entry_prices:
                            initial_entry_prices[pos_key] = entry_price
                            save_json(INITIAL_PRICE_FILE, initial_entry_prices)
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

                    rules       = LEVERAGE_RULES.get(leverage, {})
                    tp_type     = "FAST" if rules.get('tp_type') == 'fast' else "STD"
                    tp_lev_type = rules.get('tp_type', 'standard')

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
                            for _d in [tp_levels, defense_levels, initial_margins,
                                       initial_entry_prices, defense_stops]:
                                _d.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            max_prices.pop(pos_key, None)
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(MAX_PRICE_FILE, max_prices)
                            save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                            save_json(DEFENSE_STOPS_FILE, defense_stops)
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
                            for _d in [tp_levels, defense_levels, initial_margins,
                                       initial_entry_prices, defense_stops]:
                                _d.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            max_prices.pop(pos_key, None)
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(MAX_PRICE_FILE, max_prices)
                            save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                            save_json(DEFENSE_STOPS_FILE, defense_stops)
                        else:
                            print(f"   ❌ {message}")
                        continue

                    # TP
                    if pnl_percent > 0:
                        tp_trigger, tp_msg = check_tp_trigger(pnl_percent, current_tp, leverage)

                        if tp_trigger:
                            print(f"\n   {tp_msg}")
                            print(f"   ⚡ TP emri gönderiliyor...")

                            success, message = send_tp_order(client, symbol, side, amount, tp_trigger, tp_lev_type)

                            if success:
                                print(f"   ✅ {message}")
                                tp_levels[pos_key] = tp_trigger
                                save_json(TP_FILE, tp_levels)

                                if tp_trigger == 1:
                                    be_price = entry_price * (1.0008 if side == 'LONG' else 0.9992)
                                    print(f"   🛡️  Başabaş modu aktif! BE: ${be_price:.6f}")
                                    send_notification(
                                        f"💰 *KÂR AL 1 — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ %50 kapatıldı\n🛡️ Başabaş modu aktif!"
                                    )

                                elif tp_trigger == 2 and tp_lev_type == 'standard':
                                    precision = get_symbol_precision(client, symbol)
                                    remaining = round(amount * 0.50, precision)
                                    trail_ok, trail_oid = send_trailing_stop_order(
                                        client, symbol, side, remaining, current_price,
                                        callback_rate=rules.get('trailing_callback', 2.0)
                                    )
                                    if trail_ok:
                                        tp_levels[pos_key] = "TRAILING"
                                        save_json(TP_FILE, tp_levels)
                                        print(f"   🎯 TRAILING_STOP_MARKET: qty={remaining} activationPrice=${current_price:.4f} callback=%{rules.get('trailing_callback', 2.0)}")
                                    else:
                                        print(f"   ⚠️ Trailing emri gönderilemedi!")
                                    send_notification(
                                        f"💰 *KÂR AL 2 — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ %25 kapatıldı\n🎯 Trailing Stop aktif! (callback %{rules.get('trailing_callback', 2.0)})"
                                    )

                                elif tp_trigger == 2 and tp_lev_type == 'fast':
                                    send_notification(
                                        f"💰 *KÂR AL 2 (10x) — {symbol} {side}*\n"
                                        f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                        f"✅ Pozisyon tamamen kapatıldı"
                                    )
                                    for _d in [tp_levels, defense_levels, initial_margins,
                                               initial_entry_prices, defense_stops]:
                                        _d.pop(pos_key, None)
                                    max_prices = load_json(MAX_PRICE_FILE)
                                    max_prices.pop(pos_key, None)
                                    save_json(TP_FILE, tp_levels)
                                    save_json(DEFENSE_FILE, defense_levels)
                                    save_json(INITIAL_MARGIN_FILE, initial_margins)
                                    save_json(MAX_PRICE_FILE, max_prices)
                                    save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                                    save_json(DEFENSE_STOPS_FILE, defense_stops)
                            elif message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                                for _d in [tp_levels, defense_levels, initial_margins,
                                           initial_entry_prices, defense_stops]:
                                    _d.pop(pos_key, None)
                                max_prices = load_json(MAX_PRICE_FILE)
                                max_prices.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(MAX_PRICE_FILE, max_prices)
                                save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                                save_json(DEFENSE_STOPS_FILE, defense_stops)
                            elif message == "HEDGE_NOT_SUPPORTED":
                                for _d in [tp_levels, initial_margins, defense_levels,
                                           initial_entry_prices, defense_stops]:
                                    _d.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                                save_json(DEFENSE_STOPS_FILE, defense_stops)
                                print(f"   ⚠️ {symbol} {side} takipten çıkarıldı (hedge mode kısıtı)")
                            else:
                                print(f"   ❌ {message}")

                    # Başabaş kapama (TP1 sonrası fiyat geri döndüyse)
                    if current_tp == 1:
                        be_price = entry_price * (1.0008 if side == 'LONG' else 0.9992)
                        be_hit = (current_price <= be_price) if side == 'LONG' else (current_price >= be_price)
                        if be_hit:
                            logger.info(f"🛡️  BAŞABAŞ KAPAMA: {symbol} {side} — fiyat ${current_price:.6f} BE ${be_price:.6f}")
                            print(f"\n   🛡️  BAŞABAŞ! Fiyat başabaş seviyesine döndü: ${current_price:.6f} (BE: ${be_price:.6f})")
                            print(f"   ⚡ Kalan pozisyon kapatılıyor...")
                            success, message = send_stop_loss_order(client, symbol, side, amount)
                            if success or message == "POSITION_CLOSED":
                                if message == "POSITION_CLOSED":
                                    print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                                else:
                                    print(f"   ✅ {message}")
                                    send_notification(
                                        f"🛡️ *BAŞABAŞ KAPAMA — {symbol} {side}*\n"
                                        f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                        f"💰 Giriş: ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"🛡️ Başabaş: ${be_price:.4f}\n"
                                        f"✅ Kalan %50 kapatıldı"
                                    )
                                for _d in [tp_levels, defense_levels, initial_margins,
                                           initial_entry_prices, defense_stops]:
                                    _d.pop(pos_key, None)
                                max_prices = load_json(MAX_PRICE_FILE)
                                max_prices.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(MAX_PRICE_FILE, max_prices)
                                save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                                save_json(DEFENSE_STOPS_FILE, defense_stops)
                            else:
                                print(f"   ❌ {message}")
                            continue

                    # D2 sonrası break-even izleme (motor tarafı — Binance stop backup)
                    if current_tp == "BREAKEVEN":
                        initial_ep   = initial_entry_prices.get(pos_key, entry_price)
                        be_price     = (initial_ep * 0.9434 * 1.0012
                                        if side == 'LONG'
                                        else initial_ep / (0.9434 * 1.0012))
                        be_hit = (current_price >= be_price) if side == 'LONG' else (current_price <= be_price)
                        if be_hit:
                            logger.info(f"🛡️  D2 BAŞABAŞ: {symbol} {side} fiyat ${current_price:.6f} → BE ${be_price:.6f}")
                            print(f"\n   🛡️  D2 BAŞABAŞ! Fiyat başabaş seviyesine döndü: ${current_price:.6f} (BE: ${be_price:.6f})")
                            print(f"   ⚡ Pozisyon kapatılıyor...")
                            success, message = send_stop_loss_order(client, symbol, side, amount)
                            if success or message == "POSITION_CLOSED":
                                if message != "POSITION_CLOSED":
                                    send_notification(
                                        f"🛡️ *D2 BAŞABAŞ — {symbol} {side}*\n"
                                        f"📌 {leverage}x | ROE: {roe:+.2f}%\n"
                                        f"💰 Giriş (ort.): ${entry_price:.4f}\n"
                                        f"📊 Fiyat: ${current_price:.4f}\n"
                                        f"✅ Pozisyon kapatıldı"
                                    )
                                else:
                                    print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi")
                                for _d in [tp_levels, defense_levels, initial_margins,
                                           initial_entry_prices, defense_stops]:
                                    _d.pop(pos_key, None)
                                max_prices = load_json(MAX_PRICE_FILE)
                                max_prices.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(MAX_PRICE_FILE, max_prices)
                                save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                                save_json(DEFENSE_STOPS_FILE, defense_stops)
                            else:
                                print(f"   ❌ {message}")
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
                        # D2: fiyat bazlı tetikleme (initial_entry_price * 0.88)
                        if not defense_trigger and current_defense == 1:
                            price_d2, price_msg_d2 = check_d2_price_trigger(
                                current_price, pos_key, initial_entry_prices, side
                            )
                            if price_d2:
                                defense_trigger = 2
                                defense_msg     = price_msg_d2
                        # D3: fiyat bazlı tetikleme (initial_entry_price * 0.75)
                        if not defense_trigger and current_defense == 2:
                            price_d3, price_msg_d3 = check_d3_price_trigger(
                                current_price, pos_key, initial_entry_prices, side
                            )
                            if price_d3:
                                defense_trigger = 3
                                defense_msg     = price_msg_d3
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
                            # D2: TP durdur, başabaş modu + Binance stop emri
                            if defense_trigger == 2:
                                tp_levels[pos_key] = "BREAKEVEN"
                                save_json(TP_FILE, tp_levels)
                                current_tp = "BREAKEVEN"
                                logger.info(f"🔄 D2 SONRASI: {symbol} {side} TP iptal, break-even modu aktif")
                                initial_ep = initial_entry_prices.get(pos_key, entry_price)
                                be_stop = (initial_ep * 0.9434 * 1.0012
                                           if side == 'LONG'
                                           else initial_ep / (0.9434 * 1.0012))
                                oid = send_stop_market_defense(client, symbol, side, be_stop, "D2 BAŞABAŞ STOP")
                                if oid:
                                    defense_stops[pos_key] = {'level': 2, 'orderId': oid}
                                    save_json(DEFENSE_STOPS_FILE, defense_stops)
                                    print(f"   📌 D2 başabaş stop emri: ${be_stop:.4f} (orderId={oid})")
                            # D3: D2 stop iptal, yeni stop, BREAKEVEN kaldır, normal TP
                            if defense_trigger == 3:
                                old_stop = defense_stops.get(pos_key)
                                if old_stop:
                                    try:
                                        client.futures_cancel_order(
                                            symbol=symbol, orderId=old_stop['orderId']
                                        )
                                        logger.info(f"🔄 D3: D2 stop iptal — orderId={old_stop['orderId']}")
                                    except Exception as _e:
                                        logger.warning(f"D2 stop iptal edilemedi: {_e}")
                                initial_ep = initial_entry_prices.get(pos_key, entry_price)
                                be_stop3 = (initial_ep * 0.8817 * 1.0012
                                            if side == 'LONG'
                                            else initial_ep / (0.8817 * 1.0012))
                                oid3 = send_stop_market_defense(client, symbol, side, be_stop3, "D3 BAŞABAŞ STOP")
                                if oid3:
                                    defense_stops[pos_key] = {'level': 3, 'orderId': oid3}
                                    save_json(DEFENSE_STOPS_FILE, defense_stops)
                                    print(f"   📌 D3 başabaş stop emri: ${be_stop3:.4f} (orderId={oid3})")
                                tp_levels.pop(pos_key, None)
                                save_json(TP_FILE, tp_levels)
                                current_tp = 0
                                logger.info(f"🔄 D3 SONRASI: {symbol} {side} BREAKEVEN kalktı, normal TP aktif, stop=${be_stop3:.4f}")
                            try:
                                upd = client.futures_position_information(symbol=symbol)
                                new_liq = next((float(p['liquidationPrice']) for p in upd
                                    if p['symbol'] == symbol and float(p['positionAmt']) != 0
                                    and (float(p['positionAmt']) > 0) == (side == 'LONG')), 0)
                                new_mrg = next((float(p['isolatedMargin']) for p in upd
                                    if p['symbol'] == symbol and float(p['positionAmt']) != 0
                                    and (float(p['positionAmt']) > 0) == (side == 'LONG')), 0)
                            except Exception:
                                new_liq, new_mrg = 0, 0
                            # BUG3: init_margin'i Binance'ten gelen gerçek marjla güncelle
                            if new_mrg > 0:
                                init_margin = new_mrg
                                initial_margins[pos_key] = round(new_mrg, 4)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
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
                            for _d in [defense_levels, initial_margins, tp_levels,
                                       initial_entry_prices, defense_stops]:
                                _d.pop(pos_key, None)
                            max_prices = load_json(MAX_PRICE_FILE)
                            max_prices.pop(pos_key, None)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(TP_FILE, tp_levels)
                            save_json(MAX_PRICE_FILE, max_prices)
                            save_json(INITIAL_PRICE_FILE, initial_entry_prices)
                            save_json(DEFENSE_STOPS_FILE, defense_stops)
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