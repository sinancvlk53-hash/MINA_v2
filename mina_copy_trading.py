# -*- coding: utf-8 -*-
"""Copy trading — master pozisyonları follower hesaplara oransal yansıt."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
ORDER_TYPE_MARKET = "MARKET"

_engine: Optional["CopyTradingEngine"] = None


@dataclass
class FollowerAccount:
    id: str
    name: str
    client: Any
    kasa_usdt: Optional[float] = None
    testnet: bool = True

    def balance(self) -> float:
        if self.kasa_usdt is not None and self.kasa_usdt > 0:
            return float(self.kasa_usdt)
        try:
            for asset in self.client.futures_account_balance():
                if asset.get("asset") == "USDT":
                    return float(asset.get("balance") or 0)
        except Exception as exc:
            print(f"⚠️  Follower {self.name} bakiye: {exc}")
        return 0.0


def load_follower_accounts() -> List[FollowerAccount]:
    followers: List[FollowerAccount] = []
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    for i in range(1, 10):
        key = os.getenv(f"FOLLOWER_{i}_API_KEY")
        secret = os.getenv(f"FOLLOWER_{i}_SECRET") or os.getenv(f"FOLLOWER_{i}_API_SECRET")
        if not key or not secret:
            continue
        name = os.getenv(f"FOLLOWER_{i}_NAME", f"Follower {i}")
        kasa_raw = os.getenv(f"FOLLOWER_{i}_KASA") or os.getenv(f"FOLLOWER_{i}_BALANCE")
        kasa = float(kasa_raw) if kasa_raw else None
        try:
            from binance.client import Client
            from mina_binance_retry import wrap_binance_client

            raw = Client(key, secret, testnet=testnet)
            client = wrap_binance_client(raw)
            followers.append(
                FollowerAccount(
                    id=f"follower_{i}",
                    name=name,
                    client=client,
                    kasa_usdt=kasa,
                    testnet=testnet,
                )
            )
        except Exception as exc:
            print(f"⚠️  Follower {i} bağlantı hatası: {exc}")
    return followers


class CopyTradingEngine:
    def __init__(
        self,
        master_balance_fn: Callable[[], float],
        journal=None,
    ) -> None:
        self.master_balance_fn = master_balance_fn
        self.journal = journal
        self.followers = load_follower_accounts()
        self._qty_steps: Dict[str, float] = {}

    @property
    def active_count(self) -> int:
        return len(self.followers)

    def _ratio(self, follower: FollowerAccount) -> float:
        master = self.master_balance_fn()
        fb = follower.balance()
        if master <= 0 or fb <= 0:
            return 0.0
        return fb / master

    def _get_step(self, symbol: str, client: Any) -> float:
        if symbol in self._qty_steps:
            return self._qty_steps[symbol]
        try:
            from mina_exchange_info import symbol_filters
            step = symbol_filters(client, symbol)["stepSize"]
        except Exception:
            step = 0.001
        self._qty_steps[symbol] = step
        return step

    def _round_qty(self, qty: float, symbol: str, client: Any) -> float:
        step = self._get_step(symbol, client)
        if step <= 0:
            return qty
        precision = max(0, int(round(-math.log10(step)))) if step < 1 else 0
        rounded = math.floor(qty / step) * step
        return round(rounded, precision)

    def _ensure_leverage(self, follower: FollowerAccount, symbol: str, leverage: int) -> None:
        try:
            follower.client.futures_change_leverage(symbol=symbol, leverage=int(leverage))
        except Exception:
            pass

    def on_master_open(
        self,
        *,
        symbol: str,
        side: str,
        leverage: int,
        entry_price: float,
        qty: float,
        initial_margin: float,
        master_trade_id: Optional[int] = None,
    ) -> None:
        if not self.followers or qty <= 0:
            return
        for f in self.followers:
            ratio = self._ratio(f)
            if ratio <= 0:
                continue
            f_qty = self._round_qty(qty * ratio, symbol, f.client)
            if f_qty <= 0:
                continue
            self._ensure_leverage(f, symbol, leverage)
            order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
            try:
                f.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=f_qty,
                    positionSide=side,
                )
                f_margin = initial_margin * ratio
                trade_id = 0
                if self.journal:
                    trade_id = self.journal.log_follower_trade_open(
                        follower_id=f.id,
                        follower_name=f.name,
                        master_trade_id=master_trade_id,
                        symbol=symbol,
                        side=side,
                        leverage=leverage,
                        entry_price=entry_price,
                        qty=f_qty,
                        initial_margin=f_margin,
                    )
                print(f"   📋 Copy OPEN {f.name}: {symbol} {side} qty={f_qty} id={trade_id}")
            except Exception as exc:
                print(f"   ❌ Copy OPEN {f.name} {symbol}: {exc}")

    def on_master_partial_close(
        self,
        *,
        symbol: str,
        side: str,
        close_price: float,
        close_ratio: float,
        close_reason: str,
    ) -> None:
        if not self.followers:
            return
        for f in self.followers:
            try:
                for p in f.client.futures_position_information():
                    if p.get("symbol") != symbol:
                        continue
                    amt = float(p.get("positionAmt") or 0)
                    if amt == 0:
                        continue
                    pos_side = "LONG" if amt > 0 else "SHORT"
                    if pos_side != side:
                        continue
                    close_qty = self._round_qty(abs(amt) * close_ratio, symbol, f.client)
                    if close_qty <= 0:
                        continue
                    order_side = SIDE_SELL if side == "LONG" else SIDE_BUY
                    f.client.futures_create_order(
                        symbol=symbol,
                        side=order_side,
                        type=ORDER_TYPE_MARKET,
                        quantity=close_qty,
                        positionSide=side,
                    )
                    print(f"   📋 Copy PARTIAL {f.name}: {symbol} qty={close_qty} ({close_reason})")
            except Exception as exc:
                print(f"   ❌ Copy PARTIAL {f.name} {symbol}: {exc}")

    def on_master_close(
        self,
        *,
        symbol: str,
        side: str,
        close_price: float,
        close_reason: str,
        pnl_usdt: float,
    ) -> None:
        if not self.followers:
            return
        for f in self.followers:
            try:
                amt = 0.0
                entry = close_price
                for p in f.client.futures_position_information():
                    if p.get("symbol") != symbol:
                        continue
                    raw = float(p.get("positionAmt") or 0)
                    if raw == 0:
                        continue
                    pos_side = "LONG" if raw > 0 else "SHORT"
                    if pos_side != side:
                        continue
                    amt = abs(raw)
                    entry = float(p.get("entryPrice") or close_price)
                if amt <= 0:
                    continue
                order_side = SIDE_SELL if side == "LONG" else SIDE_BUY
                qty = self._round_qty(amt, symbol, f.client)
                f.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=qty,
                    positionSide=side,
                )
                ratio = self._ratio(f)
                f_pnl = pnl_usdt * ratio
                if self.journal:
                    ft_id = self.journal.get_open_follower_trade(f.id, symbol, side)
                    if ft_id:
                        self.journal.log_follower_trade_close(
                            ft_id,
                            close_price=close_price,
                            close_qty=qty,
                            close_reason=close_reason,
                            pnl_usdt=f_pnl,
                        )
                print(f"   📋 Copy CLOSE {f.name}: {symbol} qty={qty} PnL~{f_pnl:+.2f}")
            except Exception as exc:
                print(f"   ❌ Copy CLOSE {f.name} {symbol}: {exc}")

    def dashboard_snapshot(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for f in self.followers:
            balance = f.balance()
            positions = []
            floating = 0.0
            try:
                for p in f.client.futures_position_information():
                    amt = float(p.get("positionAmt") or 0)
                    if amt == 0:
                        continue
                    sym = p["symbol"]
                    side = "LONG" if amt > 0 else "SHORT"
                    entry = float(p.get("entryPrice") or 0)
                    mark = float(p.get("markPrice") or entry)
                    upnl = float(p.get("unRealizedProfit") or 0)
                    floating += upnl
                    positions.append({
                        "symbol": sym,
                        "side": side,
                        "amount": abs(amt),
                        "entryPrice": entry,
                        "markPrice": mark,
                        "pnlUSDT": upnl,
                        "leverage": int(p.get("leverage") or 1),
                    })
            except Exception as exc:
                print(f"⚠️  Follower snapshot {f.name}: {exc}")
            out.append({
                "id": f.id,
                "name": f.name,
                "balance": round(balance, 2),
                "floatingPnl": round(floating, 2),
                "positionCount": len(positions),
                "positions": positions,
            })
        return out


def init_copy_engine(master_balance_fn: Callable[[], float], journal=None) -> CopyTradingEngine:
    global _engine
    _engine = CopyTradingEngine(master_balance_fn, journal=journal)
    if _engine.active_count:
        print(f"📋 Copy trading: {_engine.active_count} follower yüklendi")
    return _engine


def get_copy_engine() -> Optional[CopyTradingEngine]:
    return _engine
