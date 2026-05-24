# -*- coding: utf-8 -*-
"""
MİNA v2 - Execution Engine - LOGGING İLE
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BinanceConfig, AccountManager
from binance.enums import *
import time
import json
from datetime import datetime
import logging

# ═══════════════════════════════════════════════
# LOGGING KURULUMU
# ═══════════════════════════════════════════════

# Log formatı
log_format = '[%(asctime)s] %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

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

def send_defense_order(client, symbol, side, defense_level, leverage):
    """Savunma emri gönder"""
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
        
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])

        max_defense = rules.get('defense_count', 0)
        if defense_level == max_defense:
            client.futures_change_margin(
                symbol=symbol,
                amount=amount_usdt,
                type=1
            )
            logger.info(f"🛡️  SAVUNMA {defense_level}: {symbol} {side} - {amount_usdt:.2f} USDT MARGIN eklendi")
            return True, f"Savunma {defense_level}: {amount_usdt:.2f} USDT margin eklendi"

        position_size = amount_usdt * leverage
        raw_qty = position_size / price
        precision = get_symbol_precision(client, symbol)
        quantity = round(raw_qty, precision)
        
        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        
        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='LONG' if side == 'LONG' else 'SHORT'
        )
        
        logger.info(f"🛡️  SAVUNMA {defense_level}: {symbol} {side} - {quantity} eklendi (${amount_usdt:.2f}) - Order: {order['orderId']}")
        return True, f"Savunma {defense_level}: {quantity} eklendi (${amount_usdt:.2f})"
        
    except Exception as e:
        logger.error(f"❌ SAVUNMA {defense_level} HATASI: {symbol} {side} - {str(e)}")
        return False, f"Hata: {str(e)}"

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

def check_defense_trigger(pnl_percent, defense_level, leverage):
    """Savunma tetikleme"""
    rules = LEVERAGE_RULES.get(leverage)
    
    if not rules or not rules.get('defense_count'):
        return 0, None
    
    if leverage in [4, 5]:
        if defense_level == 0 and pnl_percent <= -5:
            return 1, "🚨 SAVUNMA 1! (%5 düşüş)"
        if defense_level == 1 and pnl_percent <= -10:
            return 2, "🚨 SAVUNMA 2! (%10 düşüş)"
        if defense_level == 2 and pnl_percent <= -15:
            return 3, "🚨 SAVUNMA 3! (%15 düşüş)"
    elif leverage in [2, 10]:
        if defense_level == 0 and pnl_percent <= -5:
            return 1, "🚨 SAVUNMA 1! (%5 düşüş)"
        if defense_level == 1 and pnl_percent <= -10:
            return 2, "🚨 SAVUNMA 2! (%10 düşüş)"
    
    return 0, None

def main():
    logger.info("=" * 70)
    logger.info("🚀 MİNA v2 - EXECUTION ENGINE BAŞLATILDI (LOGGING AKTİF)")
    logger.info("=" * 70)
    logger.info(f"📊 Kaldıraçlar: 1x, 2x, 3x, 4x⭐, 5x, 10x")
    logger.info(f"🛑 Stop Loss: 1x=%2, 2x=%3, 3x=%2, 4x=YOK, 5x=%2, 10x=%1")
    logger.info(f"💰 TP: Standard (%3,%5) | Fast 10x (%2,%4)")
    logger.info(f"🛡️  Savunma: 2x(2), 4x(3)⭐, 5x(3), 10x(2)")
    logger.info(f"🎯 Trailing: TP2 sonrası %1")
    logger.info(f"📝 Log Dosyası: mina_bot.log")
    logger.info("=" * 70)
    
    config = BinanceConfig()
    client = config.get_client()
    
    defense_levels = load_json(DEFENSE_FILE)
    tp_levels = load_json(TP_FILE)
    
    last_message_time = 0
    check_interval = 5
    
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
                    
                    ticker = client.futures_symbol_ticker(symbol=symbol)
                    current_price = float(ticker['price'])
                    
                    pnl_percent = calculate_pnl_percent(entry_price, current_price, side)
                    
                    pos_key = f"{symbol}_{side}"
                    current_defense = defense_levels.get(pos_key, 0)
                    current_tp = tp_levels.get(pos_key, 0)
                    
                    rules = LEVERAGE_RULES.get(leverage, {})
                    tp_type = "FAST" if rules.get('tp_type') == 'fast' else "STD"
                    
                    pnl_icon = "📈" if pnl_percent > 0 else "📉"
                    side_icon = "🟢" if side == 'LONG' else "🔴"
                    
                    max_def = rules.get('defense_count', 0)
                    
                    print(f"\n{side_icon} {symbol} - {side} {leverage}x ({tp_type})")
                    print(f"   💰 Giriş: ${entry_price:.4f}")
                    print(f"   📊 Şimdi: ${current_price:.4f}")
                    print(f"   📦 Miktar: {amount}")
                    print(f"   {pnl_icon} PnL: {pnl_percent:+.2f}% (${unrealized_pnl:+.2f})")
                    print(f"   🛡️  Savunma Seviyesi: {current_defense}/{max_def}")
                    
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
                            if pos_key in tp_levels:
                                del tp_levels[pos_key]
                            if pos_key in defense_levels:
                                del defense_levels[pos_key]
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
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
                            if pos_key in tp_levels:
                                del tp_levels[pos_key]
                            if pos_key in defense_levels:
                                del defense_levels[pos_key]
                            max_prices = load_json(MAX_PRICE_FILE)
                            if pos_key in max_prices:
                                del max_prices[pos_key]
                            save_json(TP_FILE, tp_levels)
                            save_json(DEFENSE_FILE, defense_levels)
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

                                if tp_trigger == 2:
                                    max_prices = load_json(MAX_PRICE_FILE)
                                    max_prices[pos_key] = current_price
                                    save_json(MAX_PRICE_FILE, max_prices)
                                    print(f"   🎯 Trailing aktif!")
                            elif message == "POSITION_CLOSED":
                                print(f"   ⚠️ Pozisyon zaten kapalıydı, takipten silindi: {symbol} {side}")
                                if pos_key in tp_levels:
                                    del tp_levels[pos_key]
                                if pos_key in defense_levels:
                                    del defense_levels[pos_key]
                                max_prices = load_json(MAX_PRICE_FILE)
                                if pos_key in max_prices:
                                    del max_prices[pos_key]
                                save_json(TP_FILE, tp_levels)
                                save_json(DEFENSE_FILE, defense_levels)
                                save_json(MAX_PRICE_FILE, max_prices)
                            else:
                                print(f"   ❌ {message}")
                    
                    # Savunma
                    defense_trigger, defense_msg = check_defense_trigger(
                        pnl_percent, current_defense, leverage
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
                        else:
                            print(f"   ❌ {message}")
                
                print(f"{'='*70}\n")
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 Engine kullanıcı tarafından durduruldu")
            break
        except Exception as e:
            logger.error(f"❌ KRİTİK HATA: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(check_interval)

if __name__ == "__main__":
    main()