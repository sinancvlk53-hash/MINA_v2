import sys
sys.path.insert(0, '/root/MINA_v2')
from backend.config import BinanceConfig
import time

client = BinanceConfig().get_client()
positions = client.futures_position_information()
open_pos = [p for p in positions if float(p["positionAmt"]) != 0]

if not open_pos:
    print("Acik pozisyon yok.")
    sys.exit(0)

print("%d pozisyon kapatiliyor...\n" % len(open_pos))

for p in open_pos:
    sym = p["symbol"]
    amt = float(p["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    close_side = "SELL" if amt > 0 else "BUY"
    qty = abs(amt)
    try:
        order = client.futures_create_order(
            symbol=sym,
            side=close_side,
            type="MARKET",
            quantity=qty,
            positionSide=side
        )
        print("OK  %-12s %-5s  qty=%s  orderId=%s" % (sym, side, qty, order["orderId"]))
    except Exception as e:
        print("ERR %-12s %-5s  %s" % (sym, side, e))

time.sleep(2)
remaining = [p for p in client.futures_position_information() if float(p["positionAmt"]) != 0]
print("\n--- SONUC ---")
if not remaining:
    print("Tum pozisyonlar kapatildi.")
else:
    print("Hala acik (%d):" % len(remaining))
    for p in remaining:
        print("  %s  amt=%s" % (p["symbol"], p["positionAmt"]))
