# -*- coding: utf-8 -*-
import sys, paramiko, time, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('engine_main_current.py', encoding='utf-8') as f:
    src = f.read()

changes = []

# ═══════════════════════════════════════════════════════════════
# DEG 1: TP_STOP_FILE sabiti
# ═══════════════════════════════════════════════════════════════
OLD1 = 'PENDING_ORDERS_FILE = "pending_orders.json"'
NEW1 = 'PENDING_ORDERS_FILE  = "pending_orders.json"\nTP_STOP_FILE         = "tp_stop_orders.json"'
assert OLD1 in src, "DEG1 bulunamadi"
src = src.replace(OLD1, NEW1, 1)
changes.append("DEG 1 (TP_STOP_FILE sabiti): OK")

# ═══════════════════════════════════════════════════════════════
# DEG 2: Yeni fonksiyonlar (MAX_RETRY oncesine)
# ═══════════════════════════════════════════════════════════════
NEW_FUNCS = '''def send_tp1_stop_order(client, symbol, side, entry_price, remaining_qty):
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


'''

OLD2 = 'MAX_RETRY      = 3'
assert OLD2 in src, "DEG2 bulunamadi"
src = src.replace(OLD2, NEW_FUNCS + OLD2, 1)
changes.append("DEG 2 (yeni fonksiyonlar): OK")

# ═══════════════════════════════════════════════════════════════
# DEG 3: main() tp_stop_orders yukle
# ═══════════════════════════════════════════════════════════════
OLD3 = '    pending_orders  = load_json(PENDING_ORDERS_FILE)'
NEW3 = '    pending_orders  = load_json(PENDING_ORDERS_FILE)\n    tp_stop_orders  = load_json(TP_STOP_FILE)'
assert OLD3 in src, "DEG3 bulunamadi"
src = src.replace(OLD3, NEW3, 1)
changes.append("DEG 3 (tp_stop_orders yukle): OK")

# ═══════════════════════════════════════════════════════════════
# DEG 4: TP1 else dali — stop order gonder
# Emoji karakterler nedeniyle satir bazli degistirme
# ═══════════════════════════════════════════════════════════════
lines = src.split('\n')
basabas_line = None
tp2_line = None
for i, l in enumerate(lines):
    if 'Başabaş modu aktif' in l and 'be_price' in lines[i-1]:
        basabas_line = i
    if 'tp_trigger == 2' in l and i < (basabas_line or 9999):
        tp2_line = i

assert basabas_line is not None, "DEG4: Basabas satiri bulunamadi"
# tp2_line'dan basabas_line'a kadar (dahil) 5 satiri degistir
# Satirlar: if tp_trigger == 2 / print Trailing / else: / be_price= / print Başabaş
indent = '                                '
new_block = [
    f'{indent}if tp_trigger == 2:',
    f'{indent}    print(f"   Trailing aktif!")',
    f'{indent}else:',
    f'{indent}    prec      = get_symbol_precision(client, symbol)',
    f'{indent}    remaining = round(amount * 0.50, prec)',
    f'{indent}    ok, stop_id = send_tp1_stop_order(',
    f'{indent}        client, symbol, side, entry_price, remaining',
    f'{indent}    )',
    f'{indent}    if ok:',
    f'{indent}        tp_stop_orders[pos_key] = {{',
    f"{indent}            'symbol':     symbol,",
    f"{indent}            'order_id':   stop_id,",
    f"{indent}            'stop_price': entry_price,",
    f'{indent}        }}',
    f'{indent}        save_json(TP_STOP_FILE, tp_stop_orders)',
    f'{indent}        print(f"   Stop order gonderildi: stopPrice={{entry_price:.6f}} qty={{remaining}} orderId={{stop_id}}")',
    f'{indent}    else:',
    f'{indent}        print(f"   Stop order gonderilemedi!")',
]
lines[tp2_line:basabas_line+1] = new_block
src = '\n'.join(lines)
changes.append("DEG 4 (TP1 stop order): OK")

# ═══════════════════════════════════════════════════════════════
# DEG 5: Yazilim basabas blogunu sil (current_tp == 1 blogu)
# ═══════════════════════════════════════════════════════════════
lines = src.split('\n')
start_del = None
for i, l in enumerate(lines):
    if 'if current_tp == 1:' in l and i > 880:
        start_del = i
        break

assert start_del is not None, "DEG5: basabas blogu bulunamadi"
# Blogun sonunu bul: 'continue' + bos satir
end_del = start_del
for j in range(start_del+1, start_del+60):
    if j >= len(lines): break
    if lines[j].strip() == 'continue':
        # Sonraki bos satiri da dahil et
        end_del = j + 1 if (j+1 < len(lines) and lines[j+1].strip() == '') else j
        break

lines[start_del:end_del+1] = []
src = '\n'.join(lines)
changes.append(f"DEG 5 (basabas blok silindi, {end_del - start_del + 1} satir): OK")

# ═══════════════════════════════════════════════════════════════
# DEG 6a: Stop Loss kapaninca cancel_tp1_stop_order ekle
# ═══════════════════════════════════════════════════════════════
CANCEL_SNIPPET = (
    '                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)\n'
    '                            save_json(TP_STOP_FILE, tp_stop_orders)\n'
)

# Stop loss basari blogu: save_json(TP_FILE, tp_levels) satiri oncesine ekle (ilk olusum)
OLD6a = (
    '                            save_json(TP_FILE, tp_levels)\n'
    '                            save_json(DEFENSE_FILE, defense_levels)\n'
    '                            save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                            save_json(MAX_PRICE_FILE, max_prices)\n'
    '                        else:\n'
    '                            print(f"   ❌ {message}")\n'
    '                        continue\n'
    '\n'
    '                    # Trailing Stop'
)
NEW6a = (
    '                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)\n'
    '                            save_json(TP_STOP_FILE, tp_stop_orders)\n'
    '                            save_json(TP_FILE, tp_levels)\n'
    '                            save_json(DEFENSE_FILE, defense_levels)\n'
    '                            save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                            save_json(MAX_PRICE_FILE, max_prices)\n'
    '                        else:\n'
    '                            print(f"   ❌ {message}")\n'
    '                        continue\n'
    '\n'
    '                    # Trailing Stop'
)
if OLD6a in src:
    src = src.replace(OLD6a, NEW6a, 1)
    changes.append("DEG 6a (stop loss cancel): OK")
else:
    changes.append("DEG 6a (stop loss cancel): ATILDI - pattern bulunamadi")

# ═══════════════════════════════════════════════════════════════
# DEG 6b: Trailing Stop kapaninca cancel_tp1_stop_order ekle
# ═══════════════════════════════════════════════════════════════
OLD6b = (
    '                            save_json(TP_FILE, tp_levels)\n'
    '                            save_json(DEFENSE_FILE, defense_levels)\n'
    '                            save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                            save_json(MAX_PRICE_FILE, max_prices)\n'
    '                        else:\n'
    '                            print(f"   ❌ {message}")\n'
    '                        continue\n'
    '\n'
    '                    # TP'
)
NEW6b = (
    '                            cancel_tp1_stop_order(client, pos_key, tp_stop_orders)\n'
    '                            save_json(TP_STOP_FILE, tp_stop_orders)\n'
    '                            save_json(TP_FILE, tp_levels)\n'
    '                            save_json(DEFENSE_FILE, defense_levels)\n'
    '                            save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                            save_json(MAX_PRICE_FILE, max_prices)\n'
    '                        else:\n'
    '                            print(f"   ❌ {message}")\n'
    '                        continue\n'
    '\n'
    '                    # TP'
)
if OLD6b in src:
    src = src.replace(OLD6b, NEW6b, 1)
    changes.append("DEG 6b (trailing cancel): OK")
else:
    changes.append("DEG 6b (trailing cancel): ATILDI - pattern bulunamadi")

# ═══════════════════════════════════════════════════════════════
# DEG 6c: Reconciliation orphan temizligine cancel ekle
# ═══════════════════════════════════════════════════════════════
OLD6c = (
    '                for pos_key in orphaned:\n'
    '                    for _d in [defense_levels, initial_margins, tp_levels]:\n'
    '                        _d.pop(pos_key, None)\n'
    '                    max_prices.pop(pos_key, None)\n'
    '                    stop_levels.pop(pos_key, None)\n'
)
NEW6c = (
    '                for pos_key in orphaned:\n'
    '                    cancel_tp1_stop_order(client, pos_key, tp_stop_orders)\n'
    '                    for _d in [defense_levels, initial_margins, tp_levels]:\n'
    '                        _d.pop(pos_key, None)\n'
    '                    max_prices.pop(pos_key, None)\n'
    '                    stop_levels.pop(pos_key, None)\n'
)
if OLD6c in src:
    src = src.replace(OLD6c, NEW6c, 1)
    changes.append("DEG 6c (reconciliation cancel): OK")
else:
    changes.append("DEG 6c (reconciliation cancel): ATILDI - pattern bulunamadi")

# Son reconciliation save_json satirlarinda TP_STOP_FILE ekle
OLD6c2 = (
    '                save_json(DEFENSE_FILE, defense_levels)\n'
    '                save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                save_json(TP_FILE, tp_levels)\n'
    '                save_json(MAX_PRICE_FILE, max_prices)\n'
    '                save_json(STOP_LEVELS_FILE, stop_levels)\n'
)
NEW6c2 = (
    '                save_json(DEFENSE_FILE, defense_levels)\n'
    '                save_json(INITIAL_MARGIN_FILE, initial_margins)\n'
    '                save_json(TP_FILE, tp_levels)\n'
    '                save_json(MAX_PRICE_FILE, max_prices)\n'
    '                save_json(STOP_LEVELS_FILE, stop_levels)\n'
    '                save_json(TP_STOP_FILE, tp_stop_orders)\n'
)
if OLD6c2 in src:
    src = src.replace(OLD6c2, NEW6c2, 1)
    changes.append("DEG 6c2 (reconciliation save): OK")
else:
    changes.append("DEG 6c2 (reconciliation save): ATILDI")

# ═══════════════════════════════════════════════════════════════
# Dogrulama
# ═══════════════════════════════════════════════════════════════
assert 'TP_STOP_FILE' in src
assert 'send_tp1_stop_order' in src
assert 'cancel_tp1_stop_order' in src
assert 'tp_stop_orders  = load_json(TP_STOP_FILE)' in src
assert 'STOP_MARKET' in src
assert 'if current_tp == 1:' not in src, "Basabas blogu hala var!"

with open('engine_main_patched.py', 'w', encoding='utf-8') as f:
    f.write(src)

print('\n'.join(changes))
print(f'\nToplam: {len(src)} karakter (orijinal: {len(open("engine_main_current.py",encoding="utf-8").read())})')
print('engine_main_patched.py yazildi.')
