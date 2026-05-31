import sys, os, json
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, 'backend'))
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))
from config import BinanceConfig, AccountManager

config  = BinanceConfig()
client  = config.get_client()
account = AccountManager(client)

bal = account.get_usdt_balance()
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]

with open('initial_margins.json') as f: im = json.load(f)

print(f"Bakiye: ${bal:.2f} | Acik pozisyon: {len(positions)}")
print('='*78)
print(f"{'Sembol':<16} {'Side':<6} {'Lev':<4} {'Giris':>9} {'Simdi':>9} {'PnL$':>8} {'ROE%':>7} {'isoMarj':>8}")
print('-'*78)
for p in sorted(positions, key=lambda x: x['symbol']):
    symbol = p['symbol']
    side   = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    lev    = int(p['leverage'])
    entry  = float(p['entryPrice'])
    pnl    = float(p['unRealizedProfit'])
    iso    = float(p['isolatedMargin'])
    key    = symbol + '_' + side
    init_m = im.get(key, iso)
    roe    = (pnl / init_m * 100) if init_m > 0 else 0
    ticker = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    print(f"{symbol:<16} {side:<6} {lev:<4} {entry:>9.4f} {ticker:>9.4f} {pnl:>8.2f} {roe:>7.2f} {iso:>8.2f}")
print('='*78)
