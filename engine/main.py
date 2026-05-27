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
DEFENSE_FILE = "defense_levels.json"
TP_FILE = "tp_levels.json"
MAX_PRICE_FILE = "max_prices.json"
INITIAL_MARGIN_FILE = "initial_margins.json"

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
    """Stop Loss emri gönder"""
    try:
        precision = get_symbol_precision(client, symbol)
        quantity = round(amount, precision)
        
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )

        logger.info(f"🛑 STOP LOSS: {symbol} {side} - Tüm pozisyon kapatıldı ({quantity}) - Order: {order['orderId']}")
        return True, f"🛑 STOP LOSS: Tüm pozisyon kapatıldı ({quantity})"

    except Exception as e:
        error_str = str(e)
        if '-1106' in error_str:
            logger.warning(f"⚠️ STOP LOSS ATILDI: {symbol} {side} - Pozisyon zaten kapalı, takipten siliniyor.")
            return False, "POSITION_CLOSED"
        logger.error(f"❌ STOP LOSS HATASI: {symbol} {side} - {error_str}")
        return False, f"Hata: {error_str}"

def send_tp_order(client, symbol, side, current_amount, tp_level):
    """Take Profit emri gönder"""
    try:
        if tp_level == 1:
            close_percent = 0.50
        elif tp_level == 2:
            close_percent = 0.50
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
        logger.error(f"❌ TP{tp_level} HATASI: {symbol} {side} - {error_str}")
        return False, f"Hata: {error_str}"

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
                1: slot_size * 0.20,
                2: slot_size * 0.30,
                3: slot_size * 0.30
            }
        elif leverage in [2, 10]:
            defense_amounts = {
                1: slot_size * 0.30,
                2: slot_size * 0.50
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

        def do_order():
            return client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide='LONG' if side == 'LONG' else 'SHORT'
            )

        # FIX 2 — retry
        order = _execute_with_retry(do_order, label, symbol, side)
        logger.info(f"🛡️  SAVUNMA {defense_level}: {symbol} {side} - {quantity} eklendi (${amount_usdt:.2f}) - Order: {order['orderId']}")
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
        if current_price < max_price or max_price == current_price:
            max_price = current_price
            max_prices[pos_key] = max_price
            save_json(MAX_PRICE_FILE, max_prices)
    
    if side == 'LONG':
        if current_price < max_price * 0.99:
            logger.info(f"🎯 TRAILING STOP TETİKLENDİ: {pos_key} - Max: ${max_price:.4f} → Şimdi: ${current_price:.4f}")
            return True, f"📉 TRAILING! Max: ${max_price:.4f} → ${current_price:.4f}", max_price
    else:
        if current_price > max_price * 1.01:
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

def check_defense_trigger(unrealized_pnl, initial_margin, defense_level, leverage):
    """Savunma tetikleme - ROE bazlı (unrealized_pnl / initial_margin * 100)"""
    rules = LEVERAGE_RULES.get(leverage)

    if not rules or not rules.get('defense_count'):
        return 0, None
    if initial_margin <= 0:
        return 0, None

    roe = (unrealized_pnl / initial_margin) * 100  # negatif = zarar

    if leverage == 4:
        if defense_level == 0 and roe <= -5:
            return 1, f"🚨 SAVUNMA 1! (ROE {roe:.1f}%)"
        if defense_level == 1 and roe <= -15:
            return 2, f"🚨 SAVUNMA 2! (ROE {roe:.1f}%)"
        if defense_level == 2 and roe <= -25:
            return 3, f"🚨 SAVUNMA 3! (ROE {roe:.1f}%)"

    return 0, None

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
    logger.info(f"💰 TP: Standard (%3,%5) | Fast 10x (%2,%4)")
    logger.info(f"🛡️  Savunma: 2x(0), 4x(3)⭐, 5x(0), 10x(0)")
    logger.info(f"🎯 Trailing: TP2 sonrası %1")
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
    
    defense_levels = load_json(DEFENSE_FILE)
    tp_levels = load_json(TP_FILE)
    initial_margins = load_json(INITIAL_MARGIN_FILE)
    
    last_message_time = 0
    check_interval = 30
    
    while True:
        try:
            positions = get_open_positions(client)
            
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
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
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
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
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

                            success, message = send_tp_order(client, symbol, side, amount, tp_trigger)

                            if success:
                                print(f"   ✅ {message}")
                                tp_levels[pos_key] = tp_trigger
                                save_json(TP_FILE, tp_levels)
                                send_notification(
                                    f"💰 *KÂR AL {tp_trigger} — {symbol} {side}*\n"
                                    f"📌 {leverage}x | PnL: {pnl_percent:+.2f}%\n"
                                    f"💰 Giriş: ${entry_price:.4f}\n"
                                    f"📊 Fiyat: ${current_price:.4f}\n"
                                    f"📈 Kâr: ${unrealized_pnl:+.2f}\n"
                                    f"✅ %50 kapatıldı" + ("\n🎯 Trailing aktif!" if tp_trigger == 2 else "\n🛡️ Başabaş modu aktif!")
                                )
                                max_prices = load_json(MAX_PRICE_FILE)
                                max_prices[pos_key] = current_price
                                save_json(MAX_PRICE_FILE, max_prices)
                                if tp_trigger == 2:
                                    print(f"   🎯 Trailing aktif!")
                                else:
                                    be_price = entry_price * (1.0008 if side == 'LONG' else 0.9992)
                                    print(f"   🛡️  Başabaş modu aktif! BE: ${be_price:.6f}")
                            elif message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                                if pos_key in tp_levels:
                                    del tp_levels[pos_key]
                                if pos_key in defense_levels:
                                    del defense_levels[pos_key]
                                if pos_key in initial_margins:
                                    del initial_margins[pos_key]
                                max_prices = load_json(MAX_PRICE_FILE)
                                if pos_key in max_prices:
                                    del max_prices[pos_key]
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(MAX_PRICE_FILE, max_prices)
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
                                if pos_key in tp_levels:
                                    del tp_levels[pos_key]
                                if pos_key in defense_levels:
                                    del defense_levels[pos_key]
                                if pos_key in initial_margins:
                                    del initial_margins[pos_key]
                                max_prices = load_json(MAX_PRICE_FILE)
                                if pos_key in max_prices:
                                    del max_prices[pos_key]
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(INITIAL_MARGIN_FILE, initial_margins)
                                save_json(MAX_PRICE_FILE, max_prices)
                            else:
                                print(f"   ❌ {message}")
                            continue

                    # Savunma
                    defense_trigger, defense_msg = check_defense_trigger(
                        unrealized_pnl, init_margin, current_defense, leverage
                    )
                    
                    if defense_trigger:
                        print(f"\n   {defense_msg}")
                        print(f"   ⚡ Savunma emri gönderiliyor...")
                        
                        success, message = send_defense_order(
                            client, symbol, side, defense_trigger, leverage
                        )
                        
                        if success:
                            print(f"   ✅ {message}")
                            defense_levels[pos_key] = defense_trigger
                            save_json(DEFENSE_FILE, defense_levels)
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
                            if pos_key in defense_levels:
                                del defense_levels[pos_key]
                            if pos_key in initial_margins:
                                del initial_margins[pos_key]
                            if pos_key in tp_levels:
                                del tp_levels[pos_key]
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            save_json(DEFENSE_FILE, defense_levels)
                            save_json(INITIAL_MARGIN_FILE, initial_margins)
                            save_json(TP_FILE, tp_levels)
                            save_json(MAX_PRICE_FILE, max_prices)
                        elif message == "MARGIN_FAILED":
                            print(f"   ❌ D{defense_trigger} margin eklenemedi, bir sonraki döngüde tekrar denenecek: {symbol} {side}")
                        elif message == "SLOT_LIMIT":
                            # Slot limiti doldu — seviyeyi ilerlet ki tekrar denemesin
                            logger.warning(f"⛔ SLOT LİMİTİ: {symbol} {side} D{defense_trigger} iptal — seviye ilerletildi.")
                            defense_levels[pos_key] = defense_trigger
                            save_json(DEFENSE_FILE, defense_levels)
                        else:
                            print(f"   ❌ {message}")
                
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
            import traceback
            logger.error(traceback.format_exc())

            if '-1003' in err_str or 'Too many requests' in err_str:
                logger.warning("⚠️ RATE LİMİT! 60 saniye bekleniyor...")
                time.sleep(60)
            elif 'banned until' in err_str:
                import re
                match = re.search(r'banned until (\d+)', err_str)
                if match:
                    ban_until = int(match.group(1)) / 1000
                    wait = max(0, ban_until - time.time()) + 5
                    logger.warning(f"⛔ IP BAN! {int(wait)} saniye bekleniyor...")
                    time.sleep(wait)
                else:
                    time.sleep(60)
            elif 'Connection' in err_str or 'ConnectionError' in err_str:
                logger.warning("🔌 Bağlantı hatası, 15 saniye sonra tekrar denenecek...")
                time.sleep(15)
            else:
                time.sleep(check_interval)

    release_lock()

if __name__ == "__main__":
    main()