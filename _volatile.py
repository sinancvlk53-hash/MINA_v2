import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
from config import BinanceConfig

client = BinanceConfig().get_client()
tickers = client.futures_ticker()
filtered = [
    t for t in tickers
    if t['symbol'].endswith('USDT')
    and float(t['quoteVolume']) >= 20_000_000
    and t['symbol'] not in ('BTCUSDT', 'USDCUSDT')
]
filtered.sort(key=lambda x: abs(float(x['priceChangePercent'])), reverse=True)
print(f"{'Symbol':<14} {'Change%':>8} {'Volume(M)':>12}")
print('-'*38)
for t in filtered[:20]:
    chg = float(t['priceChangePercent'])
    vol = float(t['quoteVolume']) / 1_000_000
    print(f"{t['symbol']:<14} {chg:>+8.2f}% {vol:>10.1f}M")
