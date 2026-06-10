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
import os, sys, json
sys.path.insert(0, '/root/MINA_v2')
from binance.client import Client

client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'), testnet=True)

orders = [o for o in client.futures_get_open_orders() if o['symbol'] == 'XRPUSDT']
for o in orders:
    client.futures_cancel_order(symbol='XRPUSDT', orderId=o['orderId'])
    print(f"İptal: {o['side']} @ {o['price']}")

try:
    client.futures_change_leverage(symbol='XRPUSDT', leverage=4)
except Exception as e:
    print(f"Leverage: {e}")
try:
    client.futures_change_margin_type(symbol='XRPUSDT', marginType='ISOLATED')
except Exception as e:
    print(f"Margin: {e}")

account = client.futures_account()
balance = float(account['totalWalletBalance'])
slot = balance / 10
margin = slot / 5
entry = 1.1180

info = client.futures_exchange_info()
prec = 1
price_prec = 4
for s in info['symbols']:
    if s['symbol'] == 'XRPUSDT':
        for f in s['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step = float(f['stepSize'])
                step_str = str(step).rstrip('0')
                prec = len(step_str.split('.')[-1]) if '.' in step_str else 0
            if f['filterType'] == 'PRICE_FILTER':
                tick = float(f['tickSize'])
                tick_str = str(tick).rstrip('0')
                price_prec = len(tick_str.split('.')[-1]) if '.' in tick_str else 0

entry = round(entry, price_prec)
qty = round((margin * 4) / entry, prec)
print(f"Balance={balance:.2f} slot={slot:.2f} margin={margin:.4f} qty={qty} entry={entry}")

order = client.futures_create_order(
    symbol='XRPUSDT',
    side='BUY',
    type='LIMIT',
    timeInForce='GTC',
    quantity=qty,
    price=entry,
    positionSide='LONG',
)
print(f"Açıldı: BUY LONG @ {entry} qty={qty} orderId={order.get('orderId')}")

po_path = '/root/MINA_v2/pending_orders.json'
try:
    with open(po_path, encoding='utf-8') as f:
        po = json.load(f)
except Exception:
    po = {}
po['XRPUSDT_LONG'] = {
    'order_id': order.get('orderId'),
    'symbol': 'XRPUSDT',
    'side': 'LONG',
    'placed_at': __import__('time').time(),
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
