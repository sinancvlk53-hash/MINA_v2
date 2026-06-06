#!/usr/bin/env bash
# 12h report: 2026-06-05 20:00 UTC -> 2026-06-06 08:00 UTC
set -e
ROOT=/root/MINA_v2
cd "$ROOT"

echo "================================================================================"
echo "1) mina_bot.log — take_profit|trailing|defense|stop|açıldı|kapandı"
echo "    window: 2026-06-05 20-29, 2026-06-06 00-09"
echo "================================================================================"
grep -E 'take_profit|trailing_stop|defense|stop_loss|hard_stop|açıldı|kapandı' "$ROOT/mina_bot.log" 2>/dev/null \
  | grep -E '2026-06-05 2[0-9]|2026-06-06 0[0-9]' || echo "(eşleşme yok)"

echo ""
echo "================================================================================"
echo "2) DERR — kapanan işlemler (close_time >= 2026-06-05 20:00)"
echo "================================================================================"
sqlite3 -header -column "$ROOT/mina_trading_journal.db" "
SELECT symbol, side, leverage, open_price, close_price, close_reason, pnl_usdt, open_time, close_time, signal_source
FROM trades
WHERE close_time >= '2026-06-05 20:00'
ORDER BY close_time;
"

echo ""
echo "================================================================================"
echo "3) DERR — açık işlemler"
echo "================================================================================"
sqlite3 -header -column "$ROOT/mina_trading_journal.db" "
SELECT symbol, side, leverage, open_price, signal_source, open_time
FROM trades
WHERE status='open'
ORDER BY open_time;
"

echo ""
echo "================================================================================"
echo "4) Merter DCA log"
echo "================================================================================"
if [ -f "$ROOT/signal_bot/merter_dca.log" ]; then
  grep -E '2026-06-05T2[0-9]|2026-06-06T0[0-9]' "$ROOT/signal_bot/merter_dca.log" || echo "(eşleşme yok)"
else
  echo "(merter_dca.log yok)"
fi

echo ""
echo "================================================================================"
echo "5) Haluk/Merter signals_log.txt — son 30 satır (20-29 / 00-09)"
echo "================================================================================"
grep -E '2026-06-05 2[0-9]|2026-06-06 0[0-9]' "$ROOT/signal_bot/signals_log.txt" 2>/dev/null | tail -30 || echo "(eşleşme yok)"

echo ""
echo "================================================================================"
echo "6) Binance açık pozisyonlar (ham + tablo)"
echo "================================================================================"
/root/MINA_v2/venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, "/root/MINA_v2")
sys.path.insert(0, "/root/MINA_v2/backend")
os.chdir("/root/MINA_v2")
from dotenv import load_dotenv
load_dotenv("/root/MINA_v2/.env")
from config import BinanceConfig

client = BinanceConfig().get_client()
raw = client.futures_position_information()
open_pos = [p for p in raw if float(p.get("positionAmt") or 0) != 0]
print(f"acik_sayisi: {len(open_pos)}\n")
for p in sorted(open_pos, key=lambda x: x["symbol"]):
    print("--- RAW ---")
    for k in sorted(p.keys()):
        print(f"  {k}: {p[k]}")
    print()
print("--- TABLO ---")
print(f"{'Sembol':<12} {'Yon':<6} {'Lev':>4} {'Entry':>14} {'Mark':>14} {'PnL':>12} {'ROE%':>8} {'Marjin':>12}")
print("-" * 88)
total_upnl = 0.0
total_margin = 0.0
for p in sorted(open_pos, key=lambda x: x["symbol"]):
    amt = float(p["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    upnl = float(p.get("unRealizedProfit") or 0)
    lev = int(float(p.get("leverage") or 1))
    m = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
    if m <= 0 and entry > 0:
        m = abs(amt) * entry / max(lev, 1)
    roe = (upnl / m * 100) if m > 0 else 0.0
    total_upnl += upnl
    total_margin += m
    print(f"{p['symbol']:<12} {side:<6} {lev:>4}x {entry:>14.6f} {mark:>14.6f} {upnl:>+12.4f} {roe:>+7.2f}% {m:>12.4f}")
print("-" * 88)
print(f"TOPLAM unrealized PnL: {total_upnl:+.4f} USDT")
print(f"TOPLAM isolated marjin: {total_margin:.4f} USDT")
PY

echo ""
echo "================================================================================"
echo "7) Kasa durumu"
echo "================================================================================"
/root/MINA_v2/venv/bin/python - <<'PY'
import os, sys, sqlite3
sys.path.insert(0, "/root/MINA_v2")
sys.path.insert(0, "/root/MINA_v2/backend")
os.chdir("/root/MINA_v2")
from dotenv import load_dotenv
load_dotenv("/root/MINA_v2/.env")
from config import BinanceConfig, AccountManager

client = BinanceConfig().get_client()
acc = AccountManager(client)
balance = acc.get_usdt_balance()
try:
    acct = client.futures_account()
    wallet = float(acct.get("totalWalletBalance") or balance)
    avail = float(acct.get("availableBalance") or 0)
    print(f"USDT balance (AccountManager): {balance:.4f}")
    print(f"totalWalletBalance: {wallet:.4f}")
    print(f"availableBalance: {avail:.4f}")
except Exception as e:
    print(f"USDT balance: {balance:.4f}")
    print(f"futures_account err: {e}")

upnl = 0.0
for p in client.futures_position_information():
    if float(p.get("positionAmt") or 0) != 0:
        upnl += float(p.get("unRealizedProfit") or 0)
print(f"unrealized PnL toplam: {upnl:+.4f} USDT")

conn = sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
row = conn.execute(
    "SELECT COUNT(*) n, COALESCE(SUM(pnl_usdt),0) s FROM trades WHERE close_time >= '2026-06-05 20:00:00'"
).fetchone()
print(f"DERR kapanan (>= 2026-06-05 20:00): {row[0]} islem")
print(f"realized PnL son 12h (DERR): {float(row[1]):+.4f} USDT")
conn.close()
PY
