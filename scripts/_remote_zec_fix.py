#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""cd /root/MINA_v2 && source venv/bin/activate && python3 << 'PYEOF'
from dotenv import load_dotenv
load_dotenv()
import os, sys, json, time
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client

client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)
SYMBOL = 'ZECUSDT'

for o in client.futures_get_open_orders(symbol=SYMBOL):
    client.futures_cancel_order(symbol=SYMBOL, orderId=o['orderId'])
    print(f"İptal: {o['side']} @ {o['price']}")

try:
    client.futures_change_leverage(symbol=SYMBOL, leverage=4)
except Exception as e:
    print(f"Leverage: {e}")
try:
    client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
except Exception as e:
    print(f"Margin: {e}")

account = client.futures_account()
balance = float(account['totalWalletBalance'])
slot = balance / 10
margin = slot / 5

prec = 3
price_prec = 2
for s in client.futures_exchange_info()['symbols']:
    if s['symbol'] == SYMBOL:
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = float(f['stepSize'])
                step_str = str(step).rstrip('0')
                prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
            if f['filterType'] == 'PRICE_FILTER':
                tick = float(f['tickSize'])
                tick_str = str(tick).rstrip('0')
                price_prec = len(tick_str.split('.')[-1]) if '.' in tick_str else 0

orders_to_open = [
    ('SELL', 'SHORT', 541.42),
    ('BUY', 'LONG', 378.38),
]
print(f"Balance={balance:.2f} slot={slot:.2f} margin={margin:.4f}")

po_path = '/root/MINA_v2/pending_orders.json'
try:
    with open(po_path, encoding='utf-8') as f:
        po = json.load(f)
except Exception:
    po = {}

for side, pos_side, entry in orders_to_open:
    px = round(entry, price_prec)
    qty = round((margin * 4) / px, prec)
    order = client.futures_create_order(
        symbol=SYMBOL,
        side=side,
        type='LIMIT',
        timeInForce='GTC',
        quantity=qty,
        price=px,
        positionSide=pos_side,
    )
    print(f"Açıldı: {side} {pos_side} @ {px} qty={qty} orderId={order.get('orderId')}")
    po[f'{SYMBOL}_{pos_side}'] = {
        'order_id': order.get('orderId'),
        'symbol': SYMBOL,
        'side': pos_side,
        'placed_at': time.time(),
    }

with open(po_path, 'w', encoding='utf-8') as f:
    json.dump(po, f, indent=2)
print('pending_orders.json güncellendi')
PYEOF"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=120)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
report = (out or "") + ("\nERR:\n" + err if err.strip() else "")
sys.stdout.buffer.write(report.encode("utf-8", errors="replace"))
c.close()
