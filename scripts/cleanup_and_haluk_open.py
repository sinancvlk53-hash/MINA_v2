#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 1: Testnet temizlik (ZROUSDT Merter hariç kapat + JSON sıfırla, DERR dokunma)
ADIM 2: En son Haluk PDF → approved sinyaller → limit/market giriş
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEEP_SYMBOL = "ZROUSDT"
ENTRY_SLOT_RATIO = 0.20
SLOT_COUNT = 10

RESET_JSON = [
    "initial_entry_prices.json",
    "initial_margins.json",
    "defense_levels.json",
    "tp_levels.json",
    "max_prices.json",
    "stop_levels.json",
    "pending_orders.json",
    "defense_stop_orders.json",
    "position_sources.json",
    "mina_position_state.json",
]


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def step1_cleanup() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    from config import BinanceConfig

    client = BinanceConfig().get_client()

    _banner("ADIM 1 — Açık pozisyonlar (Binance Testnet)")
    positions = client.futures_position_information()
    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

    if not open_pos:
        print("(açık pozisyon yok)")
    else:
        print(f"{'SYMBOL':<14} {'SIDE':<6} {'AMT':<16} {'LEV':<4} {'ENTRY':<14} {'MARK':<14} {'MARGIN'}")
        print("-" * 90)
        for p in open_pos:
            amt = float(p["positionAmt"])
            side = "LONG" if amt > 0 else "SHORT"
            mark = float(p.get("markPrice") or 0)
            entry = float(p.get("entryPrice") or 0)
            lev = p.get("leverage", "?")
            margin = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
            keep = " [KORUNACAK]" if p["symbol"] == KEEP_SYMBOL else ""
            print(
                f"{p['symbol']:<14} {side:<6} {amt:<16.6f} {str(lev):<4} "
                f"{entry:<14.6f} {mark:<14.6f} {margin:.4f}{keep}"
            )

    _banner("ADIM 1 — Emir iptali (ZROUSDT hariç semboller)")
    try:
        open_orders = client.futures_get_open_orders()
    except Exception as e:
        open_orders = []
        print(f"open_orders hatası: {e}")

    for o in open_orders:
        sym = o.get("symbol")
        if sym == KEEP_SYMBOL:
            print(f"ATLA  {sym} orderId={o.get('orderId')} type={o.get('type')}")
            continue
        try:
            client.futures_cancel_order(symbol=sym, orderId=o["orderId"])
            print(f"İPTAL {sym} orderId={o.get('orderId')} type={o.get('type')}")
        except Exception as e:
            print(f"İPTAL HATA {sym}: {e}")

    _banner("ADIM 1 — MARKET kapat (ZROUSDT hariç)")
    to_close = [p for p in open_pos if p["symbol"] != KEEP_SYMBOL]
    if not to_close:
        print("Kapatılacak pozisyon yok (ZROUSDT dışında).")
    else:
        for p in to_close:
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
                    f"KAPANDI {sym} {side} qty={qty} orderId={order.get('orderId')} "
                    f"status={order.get('status')} avgPrice={order.get('avgPrice', '—')}"
                )
            except Exception as e:
                print(f"HATA    {sym} {side} qty={qty} → {e}")

    time.sleep(2)
    remaining = [
        p for p in client.futures_position_information()
        if float(p.get("positionAmt", 0)) != 0
    ]
    print("\n--- ADIM 1 KAPANIŞ SONUÇ ---")
    for p in remaining:
        amt = float(p["positionAmt"])
        side = "LONG" if amt > 0 else "SHORT"
        print(f"  KALAN  {p['symbol']} {side} amt={amt}")

    _banner("ADIM 1 — JSON hafıza sıfırlama (DERR dokunulmadı)")
    for fn in RESET_JSON:
        path = os.path.join(ROOT, fn)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"OK  {fn} → {{}}")

    merter_path = os.path.join(ROOT, "signal_bot", "merter_dca_state.json")
    zro_state = {"positions": {}, "pending_confirm": {}}
    # ZRO açık kaldıysa merter state'i koru (varsa oku, yoksa boş)
    if os.path.isfile(merter_path):
        try:
            old = json.load(open(merter_path, encoding="utf-8"))
            for yuva, pos in (old.get("positions") or {}).items():
                if pos and pos.get("symbol") == KEEP_SYMBOL:
                    zro_state["positions"][yuva] = pos
                    print(f"OK  merter_dca_state — {yuva}/{KEEP_SYMBOL} korundu")
        except Exception:
            pass
    with open(merter_path, "w", encoding="utf-8") as f:
        json.dump(zro_state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if not zro_state["positions"]:
        print("OK  signal_bot/merter_dca_state.json → boş (ZRO state yoktu)")

    print("DERR mina_trading_journal.db — DOKUNULMADI")


def _latest_pdf() -> str | None:
    pdf_dir = os.path.join(ROOT, "signal_bot", "pdfs")
    files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def step2_haluk_pdf() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL
    from config import AccountManager, BinanceConfig
    from mina_entry_orders import register_pending_limit, resolve_entry_order
    from mina_position_manager import MinaPositionManager
    from mina_signal_source import HT, format_open_log
    from mina_trading_journal import TradingJournal
    from signal_bot.haluk_pdf_parser import parse_haluk_pdf
    import mina_tracking as mt

    pdf_path = _latest_pdf()
    _banner("ADIM 2 — En son Haluk PDF")
    if not pdf_path:
        print("PDF bulunamadı (signal_bot/pdfs/*.pdf)")
        return

    print(f"DOSYA: {pdf_path}")
    print(f"MTIME: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(pdf_path)))}")

    result = parse_haluk_pdf(pdf_path)
    approved = [s for s in result.signals if s.get("status") == "approved"]

    print(f"\nApproved sinyal sayısı: {len(approved)}")
    if not approved:
        print("\n>>> HİÇ APPROVED SİNYAL YOK — işlem açılmadı.")
        if result.rejected:
            print("\nReddedilenler (özet):")
            for r in result.rejected[:15]:
                print(f"  {r.get('coin')} — {r.get('reason')}")
        return

    print(f"\n{'SYMBOL':<12} {'SIDE':<6} {'LEV':<4} {'ENTRY':<14} {'STOP':<10}")
    print("-" * 50)
    for s in approved:
        print(
            f"{s.get('coin','?'):<12} {s.get('side','?'):<6} "
            f"{s.get('leverage','?'):<4} {str(s.get('entry','—')):<14} {str(s.get('stop','—')):<10}"
        )

    client = BinanceConfig().get_client()
    account = AccountManager(client)
    slot = account.calculate_slot_size()
    margin_base = slot * ENTRY_SLOT_RATIO
    journal = TradingJournal(os.path.join(ROOT, "mina_trading_journal.db"))
    mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)

    _banner("ADIM 2 — Giriş emirleri (limit uzak / market yakın)")

    opened = 0
    for s in approved:
        symbol = str(s.get("coin", "")).upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        side = str(s.get("side", "LONG")).upper()
        lev = int(s.get("leverage") or 2)
        entry_price = s.get("entry_price")
        if entry_price is not None:
            try:
                entry_price = float(entry_price)
            except (TypeError, ValueError):
                entry_price = None

        # Zaten açık pozisyon varsa atla
        already_open = False
        try:
            rows = client.futures_position_information(symbol=symbol)
            for row in rows:
                amt = float(row.get("positionAmt") or 0)
                if amt == 0:
                    continue
                ps = row.get("positionSide", "BOTH")
                if ps == "BOTH":
                    pos_side = "LONG" if amt > 0 else "SHORT"
                else:
                    pos_side = ps
                if pos_side == side:
                    already_open = True
                    print(f"ATLA  {symbol} {side} — zaten açık amt={amt}")
                    break
        except Exception as e:
            print(f"WARN  {symbol} pozisyon kontrol: {e}")
        if already_open:
            continue

        try:
            client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        except Exception:
            pass
        try:
            client.futures_change_leverage(symbol=symbol, leverage=lev)
        except Exception as e:
            print(f"WARN  {symbol} leverage {lev}x: {e}")

        try:
            mark = float(client.futures_mark_price(symbol=symbol)["markPrice"])
        except Exception as e:
            print(f"HATA  {symbol} mark price: {e}")
            continue

        order_type, limit_px = resolve_entry_order(side, entry_price, mark)
        use_limit = order_type == ORDER_TYPE_LIMIT and limit_px is not None
        exec_price = float(limit_px) if use_limit else mark
        notional = margin_base * lev
        qty = mina._round_quantity(notional / exec_price, symbol)
        if qty <= 0:
            print(f"HATA  {symbol} miktar sıfır margin={margin_base:.4f} lev={lev}")
            continue

        dist_pct = abs(mark - entry_price) / mark * 100 if entry_price else 0
        order_side = SIDE_BUY if side == "LONG" else SIDE_SELL

        try:
            if use_limit:
                limit_px = mina._round_price(float(limit_px))
                order = client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_LIMIT,
                    price=limit_px,
                    quantity=qty,
                    positionSide=side,
                    timeInForce="GTC",
                )
                pk = mt.pos_key(symbol, side)
                register_pending_limit(
                    pk,
                    order_id=int(order.get("orderId") or 0),
                    symbol=symbol,
                    side=side,
                    limit_price=limit_px,
                    margin=margin_base,
                    leverage=lev,
                    meta={"signal_source": HT, "source": "haluk_pdf_batch"},
                )
                print(
                    f"LIMIT  {symbol} {side} {lev}x @{limit_px} mark={mark:.6f} "
                    f"entry_hedef={entry_price} mesafe={dist_pct:.2f}% qty={qty} "
                    f"orderId={order.get('orderId')}"
                )
            else:
                order = client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=qty,
                    positionSide=side,
                )
                time.sleep(0.3)
                mark_fill = float(client.futures_mark_price(symbol=symbol)["markPrice"])
                key = mt.pos_key(symbol, side)

                initial_prices = mt.load_json(mt.INITIAL_PRICE_FILE)
                initial_margins = mt.load_json(mt.INITIAL_MARGIN_FILE)
                defense_levels = mt.load_json(mt.DEFENSE_FILE)
                tp_levels = mt.load_json(mt.TP_FILE)
                max_prices = mt.load_json(mt.MAX_PRICE_FILE)
                initial_prices[key] = mark_fill
                initial_margins[key] = round(margin_base, 4)
                defense_levels[key] = 0
                tp_levels[key] = 0
                max_prices[key] = mark_fill
                mt.save_json(mt.INITIAL_PRICE_FILE, initial_prices)
                mt.save_json(mt.INITIAL_MARGIN_FILE, initial_margins)
                mt.save_json(mt.DEFENSE_FILE, defense_levels)
                mt.save_json(mt.TP_FILE, tp_levels)
                mt.save_json(mt.MAX_PRICE_FILE, max_prices)

                mina.init_position_state(symbol, mark_fill)
                st = mina.position_states.get(symbol, {})
                st["initial_margin"] = margin_base
                mina._save_state()
                mina.log_position_open(
                    symbol, side, lev, mark_fill, qty, margin_base, signal_source=HT
                )
                print(
                    f"MARKET {symbol} {side} {lev}x mark={mark:.6f} fill≈{mark_fill:.6f} "
                    f"entry={entry_price} mesafe={dist_pct:.2f}% qty={qty} "
                    f"orderId={order.get('orderId')} | {format_open_log(HT, symbol, side)}"
                )
                opened += 1
        except Exception as e:
            print(f"HATA  {symbol} {side} emir: {e}")

        time.sleep(0.2)

    print(f"\n--- ADIM 2 SONUÇ ---")
    print(f"MARKET ile açılan: {opened}")
    print(f"LIMIT bekleyen: pending_orders.json kontrol edin")
    pending = mt.load_json(mt.PENDING_ORDERS_FILE)
    if pending:
        for pk, info in pending.items():
            print(f"  PENDING {pk} @{info.get('limit_price')} order={info.get('order_id')}")


def main() -> None:
    step1_cleanup()
    step2_haluk_pdf()


if __name__ == "__main__":
    main()
