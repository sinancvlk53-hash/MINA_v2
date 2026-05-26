import sys
sys.stdout.reconfigure(encoding='utf-8')
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig

config = BinanceConfig()
client = config.get_client()
positions = client.futures_position_information()
open_pos = [p for p in positions if float(p["positionAmt"]) != 0]
print(f"Acik pozisyon: {len(open_pos)}")
for p in open_pos:
    side = "LONG" if float(p["positionAmt"]) > 0 else "SHORT"
    print(f"  {p['symbol']} {side} {p['leverage']}x | entry:{p['entryPrice']} | margin:{float(p['isolatedMargin']):.2f} USDT")
