#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LABUSDT hayalet isolated marjin temizliği (amt=0, negatif wallet).

Sıra:
1) Durum raporu
2) Cross futures cüzdan → LABUSDT isolated (+230 USDT)  [positionMargin type=1]
3) Isolated fazla marjini cross'a geri al                 [positionMargin type=2]
4) futures_account_transfer (spot→futures gerekirse)
5) CROSSED ↔ ISOLATED geçiş fallback
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from config import BinanceConfig, AccountManager

SYMBOL = "LABUSDT"
TOP_UP_USDT = 230.0


def banner(msg: str) -> None:
    print("\n" + "=" * 70)
    print(msg)
    print("=" * 70)


def show_labu(client) -> None:
    rows = client.futures_position_information(symbol=SYMBOL)
    if not rows:
        print(f"{SYMBOL}: kayıt yok")
        return
    for p in rows:
        amt = float(p.get("positionAmt") or 0)
        margin = float(p.get("isolatedMargin") or 0)
        wallet = float(p.get("isolatedWallet") or 0)
        print(
            f"  {p.get('positionSide'):<6} amt={amt:<12} "
            f"isolatedMargin={margin:<12} isolatedWallet={wallet}"
        )


def show_balances(client, account: AccountManager) -> None:
    try:
        bal = account.get_usdt_balance()
        print(f"  Futures USDT (cross/toplam): {bal:.4f}")
    except Exception as e:
        print(f"  Futures balance hatası: {e}")
    try:
        assets = client.futures_account_balance()
        for a in assets:
            if a.get("asset") == "USDT":
                print(
                    f"  futures_account_balance USDT: "
                    f"balance={a.get('balance')} available={a.get('availableBalance')} "
                    f"crossWallet={a.get('crossWalletBalance')}"
                )
    except Exception as e:
        print(f"  futures_account_balance: {e}")


def ensure_isolated(client) -> None:
    try:
        client.futures_change_margin_type(symbol=SYMBOL, marginType="ISOLATED")
        print("  marginType=ISOLATED OK")
    except Exception as e:
        print(f"  marginType ISOLATED: {e}")


def add_isolated_margin(client, amount: float, position_side: str) -> bool:
    """Cross → isolated symbol wallet (type=1)."""
    try:
        r = client.futures_change_position_margin(
            symbol=SYMBOL,
            amount=amount,
            type=1,
            positionSide=position_side,
        )
        print(f"  ADD +{amount} USDT → {position_side}: {r}")
        return True
    except Exception as e:
        print(f"  ADD HATA {position_side} +{amount}: {e}")
        return False


def reduce_isolated_margin(client, amount: float, position_side: str) -> bool:
    """Isolated → cross (type=2)."""
    try:
        r = client.futures_change_position_margin(
            symbol=SYMBOL,
            amount=amount,
            type=2,
            positionSide=position_side,
        )
        print(f"  REDUCE -{amount} USDT ← {position_side}: {r}")
        return True
    except Exception as e:
        print(f"  REDUCE HATA {position_side} -{amount}: {e}")
        return False


def try_spot_to_futures(client, amount: float) -> None:
    """futures_account_transfer type=1: spot → USDT-M futures."""
    banner("Spot → Futures transfer (futures_account_transfer type=1)")
    try:
        r = client.futures_account_transfer(asset="USDT", amount=amount, type=1)
        print(f"  OK transfer spot→futures {amount} USDT: {r}")
    except Exception as e:
        print(f"  HATA: {e}")


def try_cross_isolated_toggle(client) -> None:
    banner("Fallback: CROSSED ↔ ISOLATED geçiş")
    for step in ("CROSSED", "ISOLATED"):
        try:
            client.futures_change_margin_type(symbol=SYMBOL, marginType=step)
            print(f"  → {step} OK")
            time.sleep(0.8)
        except Exception as e:
            print(f"  → {step} HATA: {e}")
    show_labu(client)


def main() -> None:
    client = BinanceConfig().get_client()
    account = AccountManager(client)

    banner(f"LABUSDT HAYALET TEMİZLİK — {SYMBOL}")
    print("Başlangıç durumu:")
    show_labu(client)
    show_balances(client, account)

    ensure_isolated(client)
    time.sleep(0.5)

    rows = client.futures_position_information(symbol=SYMBOL)
    sides = []
    for p in rows:
        ps = p.get("positionSide") or "BOTH"
        margin = float(p.get("isolatedMargin") or 0)
        amt = float(p.get("positionAmt") or 0)
        if amt == 0 and margin <= 0:
            sides.append((ps, margin))

    if not sides:
        print("\nNegatif marjinli boş pozisyon yok — temiz görünüyor.")
        return

    banner(f"Adım 2 — Cross'tan isolated'a +{TOP_UP_USDT} USDT ekle")
    # Hedge: negatif tarafa ekle; BOTH modda LONG dene
    target_sides = [s[0] for s in sides] or ["LONG", "SHORT", "BOTH"]
    added = False
    for ps in target_sides:
        if add_isolated_margin(client, TOP_UP_USDT, ps):
            added = True
            break
    if not added:
        for ps in ("LONG", "SHORT"):
            if add_isolated_margin(client, TOP_UP_USDT, ps):
                added = True
                break

    time.sleep(1)
    print("\nTransfer sonrası:")
    show_labu(client)

    banner("Adım 3 — Isolated fazla marjini cross'a geri al")
    rows = client.futures_position_information(symbol=SYMBOL)
    for p in rows:
        ps = p.get("positionSide") or "BOTH"
        amt = float(p.get("positionAmt") or 0)
        margin = float(p.get("isolatedMargin") or 0)
        if amt != 0:
            continue
        if margin > 0.01:
            # Küçük buffer bırakmadan tamamını çek
            reduce_isolated_margin(client, round(margin - 0.01, 2), ps)
        elif margin < -0.01 and added:
            # Hâlâ negatif — bir kez daha ekle ve çek
            add_isolated_margin(client, abs(margin) + 10, ps)
            time.sleep(0.5)
            rows2 = client.futures_position_information(symbol=SYMBOL)
            for p2 in rows2:
                if p2.get("positionSide") == ps:
                    m2 = float(p2.get("isolatedMargin") or 0)
                    if m2 > 0.01:
                        reduce_isolated_margin(client, round(m2 - 0.01, 2), ps)

    time.sleep(1)
    print("\nReduce sonrası:")
    show_labu(client)

    # Hâlâ negatif mi?
    still_bad = False
    for p in client.futures_position_information(symbol=SYMBOL):
        if float(p.get("positionAmt") or 0) == 0:
            m = float(p.get("isolatedMargin") or 0)
            if abs(m) > 0.5:
                still_bad = True

    if still_bad:
        try_cross_isolated_toggle(client)

    banner("SON DURUM")
    show_labu(client)
    show_balances(client, account)

    still_bad = False
    for p in client.futures_position_information(symbol=SYMBOL):
        if float(p.get("positionAmt") or 0) == 0:
            m = float(p.get("isolatedMargin") or 0)
            w = float(p.get("isolatedWallet") or 0)
            if abs(m) > 0.5 or abs(w) > 0.5:
                still_bad = True
                print(f"  ⚠️  KALINTI {p.get('positionSide')} margin={m} wallet={w}")

    if still_bad:
        print(
            "\n>>> Temizlenemedi. Testnet tam sıfırlama gerekebilir "
            "(Binance testnet hesap reset / yeni API key)."
        )
    else:
        print("\n>>> LABUSDT hayalet marjin temizlendi veya sıfıra yakın.")


if __name__ == "__main__":
    main()
