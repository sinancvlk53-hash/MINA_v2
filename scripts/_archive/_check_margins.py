import sys
sys.path.insert(0, '/root/MINA_v2')
from backend.config import BinanceConfig

client = BinanceConfig().get_client()
positions = client.futures_position_information()

print("%-12s %-5s  %-12s  %-8s  %s  %s" % ("SEMBOL", "YON", "MIKTAR", "GIRIS", "LEV", "MARGIN (USDT)"))
print("-" * 70)
for p in positions:
    amt = float(p["positionAmt"])
    if amt != 0:
        sym = p["symbol"]
        ep  = float(p["entryPrice"])
        lev = int(p["leverage"])
        margin = abs(amt) * ep / lev
        side = "LONG" if amt > 0 else "SHORT"
        print("%-12s %-5s  %-12s  %-8.4f  %dx  %.2f USDT" % (sym, side, amt, ep, lev, margin))
