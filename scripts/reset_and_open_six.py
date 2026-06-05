#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testnet reset + 6 pozisyon aç (2 slot Merter boş).
ADIM 1: Tüm pozisyonları kapat
ADIM 2: JSON state sıfırla (DERR dokunulmaz)
ADIM 3: 6 pozisyon aç (3L + 3S)
ADIM 4: Merter slotları boş bırak (6/8 motor slot kullanımı)
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from open_fast_coins import (
    ENTRY_SLOT_RATIO,
    LEVERAGE,
    SLOT_COUNT,
    AccountManager,
    BinanceConfig,
    ensure_hedge_mode,
    get_step_sizes,
    try_open_with_backup,
)

SHORT_BACKUP_ALT = "POLUSDT"  # MATIC testnette kapalı olabilir

RESET_FILES = [
    "initial_entry_prices.json",
    "defense_levels.json",
    "tp_levels.json",
    "max_prices.json",
    "stop_levels.json",
    "pending_orders.json",
    "defense_stop_orders.json",
]

LONG_PLAN = [
    ("SOLUSDT", "AAVEUSDT"),
    ("INJUSDT", "AAVEUSDT"),
    ("LINKUSDT", "AAVEUSDT"),
]
SHORT_PLAN = [
    ("XRPUSDT", "MATICUSDT"),
    ("ADAUSDT", "MATICUSDT"),
    ("DOTUSDT", "MATICUSDT"),
]


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def step1_close_all(client) -> None:
    _banner("ADIM 1 — Tüm pozisyonları kapat (MARKET)")
    try:
        client.futures_cancel_all_open_orders()
        print("Tüm açık emirler iptal edildi.")
    except Exception as e:
        print(f"Emir iptal (devam): {e}")

    positions = client.futures_position_information()
    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    if not open_pos:
        print("Açık pozisyon yok.")
        return

    print(f"{len(open_pos)} pozisyon kapatılıyor...\n")
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
                positionSide=side,
            )
            print(
                f"OK  {sym:<12} {side:<5} qty={qty} orderId={order.get('orderId')} "
                f"status={order.get('status')}"
            )
        except Exception as e:
            print(f"ERR {sym:<12} {side:<5} {e}")

    time.sleep(2)
    remaining = [p for p in client.futures_position_information() if float(p.get("positionAmt", 0)) != 0]
    print("\n--- ADIM 1 SONUÇ ---")
    if not remaining:
        print("Tüm pozisyonlar kapatıldı.")
    else:
        print(f"Hâlâ açık: {len(remaining)}")
        for p in remaining:
            print(f"  {p['symbol']} amt={p['positionAmt']}")


def step2_reset_json() -> None:
    _banner("ADIM 2 — JSON hafıza temizliği")
    for fn in RESET_FILES:
        path = os.path.join(ROOT, fn)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
            f.write("\n")
        print(f"OK  {fn} → {{}}")

    merter_state = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
    empty_merter = {"positions": {}, "pending_confirm": {}}
    with open(merter_state, "w", encoding="utf-8") as f:
        json.dump(empty_merter, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"OK  signal_bot/merter_dca_state.json → sıfırlandı")
    print("DERR (mina_trading_journal.db) — DOKUNULMADI")


def step3_open_six(client, account) -> int:
    _banner("ADIM 3 — 6 yeni pozisyon aç (4x ISOLATED, slot/5 marjin)")

    balance = account.get_usdt_balance()
    slot_size = balance / SLOT_COUNT
    margin_usdt = slot_size * ENTRY_SLOT_RATIO

    print(f"BALANCE_USDT = {balance:.4f}")
    print(f"SLOT_SIZE    = {slot_size:.4f}  (balance/10)")
    print(f"ENTRY_MARGIN = {margin_usdt:.4f}  (slot×20% = slot/5)")
    print(f"LEVERAGE     = {LEVERAGE}x ISOLATED")
    print(f"MOTOR SLOTS  = 6 kullanılacak | MERTER rezerv = 2 boş\n")

    ensure_hedge_mode(client)
    step_sizes = get_step_sizes(client)
    exclude: set = set()
    opened = 0

    print("--- LONG ---")
    for primary, backup in LONG_PLAN:
        if try_open_with_backup(client, primary, backup, "LONG", margin_usdt, step_sizes, exclude):
            opened += 1
        time.sleep(0.4)

    print("\n--- SHORT ---")
    for primary, backup in SHORT_PLAN:
        ok = try_open_with_backup(client, primary, backup, "SHORT", margin_usdt, step_sizes, exclude)
        if not ok and backup == "MATICUSDT":
            ok = try_open_with_backup(
                client, primary, SHORT_BACKUP_ALT, "SHORT", margin_usdt, step_sizes, exclude
            )
        if ok:
            opened += 1
        time.sleep(0.4)

    print(f"\n--- ADIM 3 SONUÇ: {opened}/6 pozisyon gönderildi ---")
    positions = client.futures_position_information()
    open_list = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    for p in open_list:
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        print(
            f"  {p['symbol']:<12} {side:<5} amt={amt} entry={p.get('entryPrice')} "
            f"lev={p.get('leverage')} margin={p.get('isolatedMargin')}"
        )
    return opened


def step4_merter_note(open_count: int) -> None:
    _banner("ADIM 4 — Merter DCA slotları")
    print(f"Açık motor pozisyonu : {open_count}")
    print(f"Merter rezerv slot    : 2 (EI + RSI — dokunulmadı)")
    print(f"Boş slot (toplam 10)  : {10 - open_count - 2}")
    print("Gece sinyal gelince merter_dca_manager otomatik açacak.")


def main() -> None:
    config = BinanceConfig()
    client = config.get_client()
    account = AccountManager(client)
    testnet = "TESTNET" if config.testnet else "MAINNET"
    print(f"BINANCE {testnet}")

    step1_close_all(client)
    step2_reset_json()
    opened = step3_open_six(client, account)
    step4_merter_note(opened)

    _banner("TAMAMLANDI")
    bal = account.get_usdt_balance()
    cnt = sum(1 for p in client.futures_position_information() if float(p.get("positionAmt", 0)) != 0)
    print(f"FINAL_BALANCE={bal:.4f} USDT | OPEN_POSITIONS={cnt}")


if __name__ == "__main__":
    main()
