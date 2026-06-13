import sys, os, json

ROOT = os.environ.get('MINA_DATA_ROOT', '/root/MINA_v2')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'backend'))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))
from config import BinanceConfig, AccountManager

config  = BinanceConfig()
client  = config.get_client()
account = AccountManager(client)

bal = account.get_usdt_balance()
positions = [p for p in client.futures_position_information() if float(p['positionAmt']) != 0]

with open(os.path.join(ROOT, 'initial_margins.json')) as f: im = json.load(f)
with open(os.path.join(ROOT, 'position_states.json')) as f: ps = json.load(f)
with open(os.path.join(ROOT, 'defense_levels.json')) as f: dl = json.load(f)

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
    margin = float(p.get('isolatedMargin') or im.get(key, 0))
    if margin > 0:
        roe = pnl / margin * 100
    else:
        roe = 0
    ticker = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    print(f"{symbol:<16} {side:<6} {lev:<4} {entry:>9.4f} {ticker:>9.4f} {pnl:>8.2f} {roe:>7.2f} {iso:>8.2f}")
print('='*78)
