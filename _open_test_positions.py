import sys
sys.path.insert(0, '/root/MINA_v2')
from backend.config import BinanceConfig, AccountManager

config = BinanceConfig()
client = config.get_client()
account = AccountManager(client)

balance = account.get_usdt_balance()
slot = balance / 10
entry_usdt = slot / 5
leverage = 4

print("Bakiye : %.2f USDT" % balance)
print("Slot   : %.2f USDT" % slot)
print("Giris  : %.2f USDT (slot/5)" % entry_usdt)
print()

try:
    client.futures_change_position_mode(dualSidePosition=True)
    print("Hedge mode aktif edildi")
except Exception as e:
    print("Hedge mode: %s" % e)


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
    try:
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
        except Exception as e:
            if "-4028" not in str(e):
                print("  %s leverage: %s" % (symbol, e))
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker["price"])
        prec = get_precision(symbol)
        qty = round((entry_usdt * leverage) / price, prec)
        if qty <= 0:
            print("  %s %s: miktar sifir, atlandi" % (symbol, pos_side))
            return
        order = client.futures_create_order(
            symbol=symbol, side=order_side, type="MARKET",
            quantity=qty, positionSide=pos_side
        )
        oid = order["orderId"]
        print("  OK  %-12s %-5s  qty=%-10s  price=%.4f  entry=$%.2f  id=%s" % (
            symbol, pos_side, qty, price, entry_usdt, oid))
    except Exception as e:
        print("  ERR %-12s %-5s  %s" % (symbol, pos_side, e))


longs  = ["HUSDT", "TAUSDT", "CLOUSDT", "LABUSDT"]
shorts = ["STGUSDT", "NFPUSDT", "VTHUSDT", "JCTUSDT"]
hedges = ["MYXUSDT"]

print("\n=== LONG ===")
for s in longs:
    open_pos(s, "BUY", "LONG")

print("\n=== SHORT ===")
for s in shorts:
    open_pos(s, "SELL", "SHORT")

print("\n=== HEDGE ===")
for s in hedges:
    open_pos(s, "BUY",  "LONG")
    open_pos(s, "SELL", "SHORT")

print("\n=== ACIK POZISYONLAR ===")
positions = client.futures_position_information()
open_list = [p for p in positions if float(p["positionAmt"]) != 0]
if not open_list:
    print("Acik pozisyon yok")
else:
    for p in open_list:
        sym  = p["symbol"]
        amt  = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        ep   = float(p["entryPrice"])
        lev  = p["leverage"]
        print("  %-12s %-5s  amt=%-12s  entry=%.4f  lev=%sx" % (sym, side, amt, ep, lev))
