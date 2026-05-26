# -*- coding: utf-8 -*-
"""
MINA v2 - 10 Pozisyon Test Script
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BinanceConfig, AccountManager
from binance.enums import *
import time
import json

# ─── JSON DOSYALARI ──────────────────────────────────────────────────────────
JSON_FILES = [
    "defense_levels.json",
    "initial_margins.json",
    "tp_levels.json",
    "max_prices.json",
]

# ─── TEST POZİSYONLARI ───────────────────────────────────────────────────────
MAX_SLOTS = 10  # Maksimum açık pozisyon sayısı

POSITIONS = [
    {"no": 1,  "symbol": "AKTUSDT",   "side": "LONG",  "leverage": 1,  "not": "SL %3"},
    {"no": 2,  "symbol": "DEXEUSDT",  "side": "SHORT", "leverage": 2,  "not": "SL %3"},
    {"no": 3,  "symbol": "SAGAUSDT",  "side": "LONG",  "leverage": 3,  "not": "SL %2"},
    {"no": 4,  "symbol": "SKYUSDT",   "side": "LONG",  "leverage": 4,  "not": "HEDGE LONG"},
    {"no": 5,  "symbol": "SKYUSDT",   "side": "SHORT", "leverage": 4,  "not": "HEDGE SHORT"},
    {"no": 6,  "symbol": "PHAUSDT",   "side": "SHORT", "leverage": 5,  "not": "SL %2"},
    {"no": 7,  "symbol": "PLUMEUSDT", "side": "LONG",  "leverage": 10, "not": "SL %1, Fast TP"},
    {"no": 8,  "symbol": "AGTUSDT",   "side": "LONG",  "leverage": 4,  "not": "3 Savunma, SL yok"},
    {"no": 9,  "symbol": "PLAYUSDT",  "side": "LONG",  "leverage": 4,  "not": "3 Savunma, SL yok"},
    {"no": 10, "symbol": "GUAUSDT",   "side": "LONG",  "leverage": 4,  "not": "3 Savunma, SL yok"},
    # 11. pozisyon — slot limiti testi, REDDEDİLMELİ
    {"no": 11, "symbol": "BTCUSDT",   "side": "LONG",  "leverage": 4,  "not": "SLOT LİMİT TESTİ"},
]

# ─── YARDIMCI FONKSİYONLAR ───────────────────────────────────────────────────

def get_symbol_step_size(client, symbol):
    exchange_info = client.futures_exchange_info()
    for s in exchange_info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    step_str = str(step_size).rstrip('0')
                    precision = len(step_str.split('.')[-1]) if '.' in step_str else 0
                    return precision
    return 3

def open_position(client, account, symbol, side, leverage, max_retry=3):
    """Tek pozisyon aç — retry destekli"""
    balance = account.get_usdt_balance()
    slot_size = balance / 10
    amount_usdt = slot_size * 0.20

    # Kaldıraç
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except Exception as e:
        print(f"   ⚠️  Kaldıraç: {e}")

    # Margin type
    try:
        client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
    except Exception:
        pass

    # Quantity (sadece bir kez hesapla)
    ticker = client.futures_symbol_ticker(symbol=symbol)
    price = float(ticker['price'])
    position_size = amount_usdt * leverage
    raw_qty = position_size / price
    precision = get_symbol_step_size(client, symbol)
    quantity = round(raw_qty, precision)
    order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL

    # Retry döngüsü
    for attempt in range(1, max_retry + 1):
        try:
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide='LONG' if side == 'LONG' else 'SHORT'
            )
            return True, {
                "order_id": order['orderId'],
                "price":    round(price, 6),
                "quantity": quantity,
                "margin":   round(amount_usdt, 2),
                "leverage": leverage,
            }
        except Exception as e:
            err = str(e)
            if attempt < max_retry:
                print(f"   ⏳ Deneme {attempt}/{max_retry} başarısız ({err[:60]}), 3s bekleniyor...")
                time.sleep(3)
            else:
                return False, err

# ─── ADIM 1: KONTROL ─────────────────────────────────────────────────────────

def step1_check(client, account):
    print("\n" + "═"*60)
    print("ADIM 1: KONTROL")
    print("═"*60)

    # Pozisyon kontrolü
    positions = client.futures_position_information()
    open_positions = [p for p in positions if float(p['positionAmt']) != 0]
    pos_ok = len(open_positions) == 0
    print(f"\n📊 Açık Pozisyon: {len(open_positions)}  {'✅ TEMİZ' if pos_ok else '❌ POZİSYON VAR!'}")
    if not pos_ok:
        for p in open_positions:
            print(f"   ⚠️  {p['symbol']} | {p['positionAmt']} | {p['unRealizedProfit']} USDT")

    # Bakiye
    balance = account.get_usdt_balance()
    slot_size = balance / 10
    entry_per_slot = slot_size * 0.20
    print(f"\n💰 Bakiye:        {balance:.2f} USDT")
    print(f"   Slot Büyüklüğü: {slot_size:.2f} USDT (bakiye / 10)")
    print(f"   Giriş/Slot:     {entry_per_slot:.2f} USDT (slot x %20)")

    # JSON dosyaları
    print(f"\n📁 JSON Dosyaları:")
    json_all_missing = True
    for fname in JSON_FILES:
        exists = os.path.exists(fname)
        if exists:
            json_all_missing = False
        print(f"   {'❌ VAR' if exists else '✅ YOK'}  {fname}")

    print()
    if not pos_ok:
        print("❌ DUR! Açık pozisyon var. Önce kapatın!")
        return False
    if not json_all_missing:
        print("⚠️  UYARI: JSON dosyaları mevcut. Devam etmek için 'evet' yazın.")
        ans = input("   Devam? (evet): ").strip().lower()
        if ans != "evet":
            print("❌ İptal edildi.")
            return False

    print("✅ Kontrol geçti. Pozisyonlar açılacak.\n")
    return True

# ─── ADIM 2: POZİSYONLARI AÇ ─────────────────────────────────────────────────

def step2_open(client, account):
    print("═"*60)
    print("ADIM 2: POZİSYONLARI AÇIYOR")
    print("═"*60)
    print(f"  {'No':>3}  {'Symbol':<12} {'Side':<6} {'Lev':>4}  {'Not'}")
    print(f"  {'-'*3}  {'-'*12} {'-'*6} {'-'*4}  {'-'*25}")
    for p in POSITIONS:
        print(f"  {p['no']:>3}. {p['symbol']:<12} {p['side']:<6} {p['leverage']:>3}x  {p['not']}")
    print()

    results = []
    open_count = 0  # açılan pozisyon sayacı

    for i, pos in enumerate(POSITIONS, 1):
        symbol   = pos['symbol']
        side     = pos['side']
        leverage = pos['leverage']
        total    = len(POSITIONS)

        print(f"[{i:2d}/{total}] {symbol} {side} {leverage}x ...", end=" ", flush=True)

        # ── SLOT SAYISI KONTROLÜ ──────────────────────────────────────────
        if open_count >= MAX_SLOTS:
            msg = f"SLOT LİMİTİ DOLDU! ({open_count}/{MAX_SLOTS}) — pozisyon reddedildi"
            print(f"⛔  {msg}")
            results.append({
                "no": i, "symbol": symbol, "side": side, "leverage": leverage,
                "not": pos['not'], "success": False, "data": msg,
            })
            continue
        # ─────────────────────────────────────────────────────────────────

        success, data = open_position(client, account, symbol, side, leverage)

        if success:
            print(f"✅  OrderID:{data['order_id']}  Qty:{data['quantity']}  Margin:{data['margin']} USDT  @{data['price']}")
            open_count += 1
        else:
            print(f"❌  HATA: {data}")

        results.append({
            "no":      i,
            "symbol":  symbol,
            "side":    side,
            "leverage":leverage,
            "not":     pos['not'],
            "success": success,
            "data":    data,
        })

        time.sleep(0.5)

    return results

# ─── ADIM 3: RAPOR ────────────────────────────────────────────────────────────

def step3_report(results):
    print("\n" + "═"*70)
    print("ADIM 3: RAPOR")
    print("═"*70)

    ok     = [r for r in results if r['success']]
    fail   = [r for r in results if not r['success'] and 'SLOT' not in str(r['data'])]
    denied = [r for r in results if 'SLOT' in str(r['data'])]

    # Tablo
    print(f"\n{'No':>3}  {'Symbol':<12} {'Side':<6} {'Lev':>4}  {'Durum':<8}  {'OrderID':<14}  {'Margin':>9}  {'Qty'}")
    print(f"{'─'*3}  {'─'*12} {'─'*6} {'─'*4}  {'─'*8}  {'─'*14}  {'─'*9}  {'─'*10}")

    for r in results:
        if r['success']:
            d = r['data']
            print(f"{r['no']:>3}. {r['symbol']:<12} {r['side']:<6} {r['leverage']:>3}x  {'✅ AÇIK':<8}  {str(d['order_id']):<14}  {d['margin']:>8.2f}$  {d['quantity']}")
        else:
            print(f"{r['no']:>3}. {r['symbol']:<12} {r['side']:<6} {r['leverage']:>3}x  {'❌ HATA':<8}  {str(r['data'])[:40]}")

    # Özet
    print(f"\n{'─'*70}")
    print(f"✅ Açıldı:        {len(ok)}/{MAX_SLOTS}")
    print(f"⛔ Slot reddi:    {len(denied)} (beklenen)")
    print(f"❌ Başarısız:     {len(fail)}")

    # Hedge kontrolü
    play_long  = any(r['symbol'] == 'PLAYUSDT' and r['side'] == 'LONG'  and r['success'] for r in results)
    play_short = any(r['symbol'] == 'PLAYUSDT' and r['side'] == 'SHORT' and r['success'] for r in results)
    hedge_ok = play_long and play_short
    print(f"🔀 Hedge (PLAYUSDT L+S): {'✅ ÇALIŞIYOR' if hedge_ok else '❌ SORUN VAR'}")

    # Kaldıraç doğrulama
    lev_ok = all(
        r['data']['leverage'] == r['leverage']
        for r in ok
    )
    print(f"⚙️  Kaldıraçlar doğru: {'✅' if lev_ok else '⚠️  Kontrol et'}")

    if denied:
        print(f"⛔ Reddedilenler:")
        for r in denied:
            print(f"   {r['no']:>2}. {r['symbol']} {r['side']} — {r['data']}")
    print(f"{'─'*70}")
    if len(ok) == MAX_SLOTS and len(denied) == len(POSITIONS) - MAX_SLOTS:
        print(f"🎉 {MAX_SLOTS} POZİSYON AÇILDI + SLOT LİMİTİ DOĞRULANDI!")
    elif len(ok) == MAX_SLOTS:
        print(f"🎉 TÜM {MAX_SLOTS} POZİSYON BAŞARIYLA AÇILDI!")
    else:
        print(f"⚠️  {len(fail)} pozisyon açılamadı!")
    print("═"*70)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("═"*60)
    print("  MİNA v2 — 10 POZİSYON TEST SCRIPT")
    print("═"*60)

    config  = BinanceConfig()
    client  = config.get_client()
    account = AccountManager(client)

    ok = step1_check(client, account)
    if not ok:
        return

    results = step2_open(client, account)
    step3_report(results)

if __name__ == "__main__":
    main()
