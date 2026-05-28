import json
import asyncio
from datetime import datetime
import sys
sys.path.append('backend')
from config import BinanceConfig

TRACKER_FILE = 'signal_bot/tracked_signals.json'

def load_tracked():
    try:
        with open(TRACKER_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_tracked(data):
    with open(TRACKER_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def open_virtual_position(coin, side, source):
    tracked = load_tracked()
    config = BinanceConfig()
    client = config.get_client()

    try:
        ticker = client.futures_symbol_ticker(symbol=coin)
        entry_price = float(ticker['price'])
    except:
        return None

    pos_key = f"{coin}_{side}_{datetime.now().strftime('%H%M%S')}"

    tracked[pos_key] = {
        'coin': coin,
        'side': side,
        'source': source,
        'entry_price': entry_price,
        'open_time': datetime.now().isoformat(),
        'max_roe': 0,
        'min_roe': 0,
        'tp1_hit': False,
        'tp2_hit': False,
        'status': 'OPEN',
        'close_price': None,
        'close_time': None,
        'close_reason': None,
        'snapshots': []
    }

    save_tracked(tracked)
    print(f"[TRACKER] Hayali pozisyon açıldı: {coin} {side} @ ${entry_price}")
    return pos_key

async def track_positions():
    config = BinanceConfig()
    client = config.get_client()

    while True:
        tracked = load_tracked()
        open_positions = {k: v for k, v in tracked.items() if v['status'] == 'OPEN'}

        for pos_key, pos in open_positions.items():
            coin = pos['coin']
            side = pos['side']
            entry = pos['entry_price']

            try:
                ticker = client.futures_symbol_ticker(symbol=coin)
                current_price = float(ticker['price'])
            except:
                continue

            if side == 'LONG':
                roe = ((current_price - entry) / entry) * 100 * 4
            else:
                roe = ((entry - current_price) / entry) * 100 * 4

            pos['snapshots'].append({
                'time': datetime.now().isoformat(),
                'price': current_price,
                'roe': round(roe, 2)
            })

            if roe > pos['max_roe']:
                pos['max_roe'] = round(roe, 2)
            if roe < pos['min_roe']:
                pos['min_roe'] = round(roe, 2)

            if not pos['tp1_hit'] and roe >= 3:
                pos['tp1_hit'] = True
                print(f"[TRACKER] TP1 HIT! {coin} {side} ROE: {roe:.2f}%")

            if not pos['tp2_hit'] and roe >= 5:
                pos['tp2_hit'] = True
                pos['status'] = 'CLOSED'
                pos['close_price'] = current_price
                pos['close_time'] = datetime.now().isoformat()
                pos['close_reason'] = 'TP2'
                print(f"[TRACKER] TP2 HIT! KAPANDI {coin} {side} ROE: {roe:.2f}%")

            if roe <= -25:
                pos['status'] = 'CLOSED'
                pos['close_price'] = current_price
                pos['close_time'] = datetime.now().isoformat()
                pos['close_reason'] = 'D3'
                print(f"[TRACKER] D3! ZARAR {coin} {side} ROE: {roe:.2f}%")

            tracked[pos_key] = pos

        save_tracked(tracked)
        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(track_positions())
