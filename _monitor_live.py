import sys, json
sys.path.insert(0, '/root/MINA_v2')
from backend.config import BinanceConfig, AccountManager

client  = BinanceConfig().get_client()
account = AccountManager(client)
balance = account.get_usdt_balance()

def rj(f):
    try:
        return json.load(open(f))
    except Exception:
        return {}

defense_levels       = rj('/root/MINA_v2/defense_levels.json')
initial_entry_prices = rj('/root/MINA_v2/initial_entry_prices.json')
initial_margins      = rj('/root/MINA_v2/initial_margins.json')

positions = [p for p in client.futures_position_information() if float(p["positionAmt"]) != 0]

print("BAKIYE: %.2f USDT" % balance)
print("ACIK  : %d pozisyon" % len(positions))
print()

for p in positions:
    amt   = float(p["positionAmt"])
    side  = "LONG" if amt > 0 else "SHORT"
    sym   = p["symbol"]
    key   = sym + "_" + side
    ep    = float(p["entryPrice"])
    mark  = float(p.get("markPrice", 0))
    upnl  = float(p["unRealizedProfit"])
    iso_m = float(p.get("isolatedMargin", 0))
    lev   = int(p["leverage"])
    liq   = float(p.get("liquidationPrice", 0))

    init_m  = initial_margins.get(key, iso_m if iso_m > 0 else abs(amt)*ep/lev)
    roe     = upnl / init_m * 100 if init_m > 0 else 0
    init_ep = initial_entry_prices.get(key, ep)
    d_lvl   = defense_levels.get(key, 0)

    if side == "LONG":
        d2_price = init_ep * 0.88
        d3_price = init_ep * 0.75
        dist_d1  = roe - (-20.0)
        dist_d2  = (mark - d2_price) / mark * 100
        dist_d3  = (mark - d3_price) / mark * 100
    else:
        d2_price = init_ep * 1.12
        d3_price = init_ep * 1.25
        dist_d1  = roe - (-20.0)
        dist_d2  = (d2_price - mark) / mark * 100
        dist_d3  = (d3_price - mark) / mark * 100

    print("=" * 48)
    print("%-14s %s  %dx" % (sym, side, lev))
    print("-" * 48)
    print("  Giris Fiyati  : $%.4f" % ep)
    print("  Mark Fiyati   : $%.4f" % mark)
    print("  Init Entry    : $%.4f  (D2/D3 referansi)" % init_ep)
    print("  PnL           : %+.2f USDT" % upnl)
    print("  ROE           : %+.1f%%  (margin: $%.2f)" % (roe, init_m))
    print("  Likidayon     : $%.4f" % liq)
    print("  Defense Seviy.: %d/3" % d_lvl)
    print()
    print("  D1 esigi      : ROE -20%%  (simdi %+.1f%%, uzaklik %+.1f%%)" % (roe, dist_d1))
    print("  D2 fiyati     : $%.4f  (%s%%12 = simdi %+.1f%% uzakta)" % (
        d2_price, "-%%" if side == "LONG" else "+%%", dist_d2))
    print("  D3 fiyati     : $%.4f  (%s%%25 = simdi %+.1f%% uzakta)" % (
        d3_price, "-%%" if side == "LONG" else "+%%", dist_d3))

    if dist_d1 < 5:
        print("  *** UYARI: D1 esigine %.1f%% kaldi! ***" % dist_d1)
    if dist_d2 < 3:
        print("  *** UYARI: D2 fiyatina %.1f%% kaldi! ***" % dist_d2)
    print()

print("=" * 48)
print("Floating PnL toplam: %+.2f USDT" % sum(float(p["unRealizedProfit"]) for p in positions))
