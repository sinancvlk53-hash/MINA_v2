import sys, time
sys.path.insert(0, '/root/MINA_v2')
from backend.config import BinanceConfig, AccountManager

client  = BinanceConfig().get_client()
account = AccountManager(client)

balance    = account.get_usdt_balance()
slot       = balance / 10
entry_usdt = slot / 5
leverage   = 4

print("Bakiye : %.2f USDT" % balance)
print("Slot   : %.2f USDT" % slot)
print("Giris  : %.2f USDT (slot/5)\n" % entry_usdt)

# Mevcut acik pozisyonlari al
existing = {}
for p in client.futures_position_information():
    amt = float(p["positionAmt"])
    if amt != 0:
        sym  = p["symbol"]
        side = "LONG" if amt > 0 else "SHORT"
        existing["%s_%s" % (sym, side)] = amt

print("Mevcut acik pozisyonlar: %s\n" % (list(existing.keys()) or "YOK"))


def get_precision(symbol):
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                for f in s["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        step = f["stepSize"].rstrip("0")
                        if "." in step:
                            return len(step.split(".")[-1])
                        return 0
    except Exception:
        pass
    return 3


def open_pos(symbol, order_side, pos_side):
    key = "%s_%s" % (symbol, pos_side)
    if key in existing:
        print("  SKIP %-12s %-5s  zaten acik (amt=%s)" % (symbol, pos_side, existing[key]))
        return True

    try:
        # Isolated margin ayarla
        try:
            client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        except Exception as e:
            if "-4046" not in str(e):   # -4046 = zaten isolated
                print("  WARN %s margin type: %s" % (symbol, e))

        # Leverage ayarla
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
        except Exception as e:
            if "-4028" not in str(e):
                print("  WARN %s leverage: %s" % (symbol, e))

        # Fiyat ve miktar
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price  = float(ticker["price"])
        prec   = get_precision(symbol)
        qty    = round((entry_usdt * leverage) / price, prec)

        if qty <= 0:
            print("  ERR  %-12s %-5s  miktar sifir" % (symbol, pos_side))
            return False

        order = client.futures_create_order(
            symbol=symbol,
            side=order_side,
            type="MARKET",
            quantity=qty,
            positionSide=pos_side
        )
        oid = order["orderId"]
        print("  OK   %-12s %-5s  qty=%-10s  price=%.4f  entry=$%.2f  id=%s" % (
            symbol, pos_side, qty, price, entry_usdt, oid))
        return True

    except Exception as e:
        print("  ERR  %-12s %-5s  %s" % (symbol, pos_side, e))
        return False


longs  = ["HUSDT",   "TAUSDT", "LABUSDT", "LTCUSDT"]
shorts = ["STGUSDT", "NFPUSDT", "JCTUSDT", "BCHUSDT"]
hedges = [("MYXUSDT", "BEATUSDT")]   # ilk dene, basarisiz olursa ikinci

print("=== LONG ===")
for s in longs:
    open_pos(s, "BUY", "LONG")

print("\n=== SHORT ===")
for s in shorts:
    open_pos(s, "SELL", "SHORT")

print("\n=== HEDGE ===")
primary, fallback = hedges[0]
ok_long  = open_pos(primary, "BUY",  "LONG")
ok_short = open_pos(primary, "SELL", "SHORT")
if not ok_long or not ok_short:
    print("  %s basarisiz, %s deneniyor..." % (primary, fallback))
    open_pos(fallback, "BUY",  "LONG")
    open_pos(fallback, "SELL", "SHORT")

# Son kontrol
time.sleep(2)
print("\n=== ACIK POZISYONLAR (FINAL) ===")
final = [p for p in client.futures_position_information() if float(p["positionAmt"]) != 0]
if not final:
    print("Hic acik pozisyon yok!")
else:
    print("%-12s %-5s  %-12s  %-8s  %-4s  %s" % (
          "SEMBOL", "YON", "MIKTAR", "GIRIS", "LEV", "MARGIN(USDT)"))
    print("-" * 65)
    for p in final:
        amt  = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        ep   = float(p["entryPrice"])
        lev  = int(p["leverage"])
        margin = abs(amt) * ep / lev
        print("%-12s %-5s  %-12s  %-8.4f  %-4dx  %.2f" % (
              p["symbol"], side, amt, ep, lev, margin))
