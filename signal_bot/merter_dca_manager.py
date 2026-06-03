# -*- coding: utf-8 -*-
"""
MINA v2 — Merter 1x DCA Modülü (EI tarama + RSI bot yuvaları)

2 slot (balance/10 each), her yuva 10 parça, 1x ISOLATED, stop yok.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from binance.enums import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, SIDE_BUY, SIDE_SELL

from signal_bot.signal_parser import (
    RE_EI_AL_SECTION,
    RE_RSI_ENTRY,
    _extract_usdt_symbols,
    _parse_num,
    normalize_symbol,
)

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SIGNAL_BOT_DIR, "merter_dca_state.json")
LOG_FILE = os.path.join(SIGNAL_BOT_DIR, "merter_dca.log")
FILTER_LOG = os.path.join(SIGNAL_BOT_DIR, "merter_dca_filter.log")

TOTAL_SLOTS = 10
PARTS_PER_YUVA = 10
LEVERAGE = 1
RVOL_MIN = 2.0
DCA_STEP = 0.02
TP1_PCT = 0.03
TP2_PCT = 0.05
TRAIL_PCT = 0.02
MAX_HOLD_H = 48
RSI_PERIOD = 14
RSI_OVERSOLD = 20.0
DOUBLE_CONFIRM_SEC = 900
MIN_24H_VOLUME_USD = 50_000_000
PUMP_15M_PCT = 0.05
PUMP_LOOKBACK_5M = 3  # 3 × 5m = 15 dakika

YUVA_EI = "merter_ei"
YUVA_RSI = "merter_rsi"

_manager: Optional["MerterDCAManager"] = None


def get_merter_dca_manager() -> "MerterDCAManager":
    global _manager
    if _manager is None:
        _manager = MerterDCAManager()
    return _manager


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _log_reject(source: str, symbol: str, reason: str, detail: Optional[Dict] = None) -> None:
    line = f"[{_now_iso()}] REJECT {source} {symbol} — {reason}"
    if detail:
        line += f" | {json.dumps(detail, ensure_ascii=False)}"
    print(line, flush=True)
    try:
        with open(FILTER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _calc_ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    ema = sum(values[:period]) / period
    m = 2 / (period + 1)
    for v in values[period:]:
        ema = v * m + ema * (1 - m)
    return ema


def _calc_rsi(closes: List[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    if len(closes) < period + 1:
        return [None] * len(closes)
    out: List[Optional[float]] = [None] * period
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        if avg_l == 0:
            rsi = 100.0
        else:
            rs = avg_g / avg_l
            rsi = 100.0 - (100.0 / (1.0 + rs))
        out.append(rsi)
    return out


def _rsi_confirmation(closes: List[float]) -> bool:
    """RSI<20 sonrası 1-2 mumda +3 puan veya 20 kırılımı."""
    rsis = _calc_rsi(closes, RSI_PERIOD)
    valid = [(i, r) for i, r in enumerate(rsis) if r is not None]
    if len(valid) < 4:
        return False
    for idx in range(len(valid) - 3, len(valid) - 1):
        i, r = valid[idx]
        if r >= RSI_OVERSOLD:
            continue
        for j in range(1, 3):
            if idx + j >= len(valid):
                break
            _, r_next = valid[idx + j]
            if r_next >= RSI_OVERSOLD or r_next >= r + 3.0:
                return True
    return False


class MerterDCAManager:
    """Merter EI + RSI 1x DCA yönetimi."""

    def __init__(self, data_root: Optional[str] = None) -> None:
        self.data_root = data_root or _ROOT
        self.state_file = STATE_FILE
        self.state = self._load_state()
        self._client: Any = None
        self._journal: Any = None
        self._step_cache: Dict[str, float] = {}

    def _load_state(self) -> Dict[str, Any]:
        if os.path.isfile(self.state_file):
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"positions": {}, "pending_confirm": {}}

    def _save_state(self) -> None:
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _client_get(self) -> Any:
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(_ROOT, ".env"))
            from config import BinanceConfig
            self._client = BinanceConfig().get_client()
        return self._client

    def _journal_get(self) -> Any:
        if self._journal is None:
            from mina_trading_journal import TradingJournal
            db = os.path.join(self.data_root, "mina_trading_journal.db")
            self._journal = TradingJournal(db_path=db)
        return self._journal

    def slot_budget(self) -> float:
        from config import AccountManager
        bal = AccountManager(self._client_get()).get_usdt_balance()
        return bal / TOTAL_SLOTS

    def part_usdt(self) -> float:
        return self.slot_budget() / PARTS_PER_YUVA

    def calculate_rvol(self, symbol: str) -> Optional[float]:
        """RVOL = son kapalı 5m hacim / son 1 saat ortalama 5m hacmi."""
        try:
            kl = self._client_get().futures_klines(symbol=symbol, interval="5m", limit=14)
        except Exception as e:
            _log_reject("rvol", symbol, f"klines hatası: {e}")
            return None
        if len(kl) < 13:
            return None
        closed = kl[:-1]
        vols = [float(k[7]) for k in closed[-12:]]
        if not vols:
            return None
        avg = sum(vols) / len(vols)
        if avg <= 0:
            return None
        last_vol = float(closed[-1][7])
        return last_vol / avg

    def get_24h_volume_usd(self, symbol: str) -> Optional[float]:
        """Futures 24s quote hacmi (USDT)."""
        try:
            tickers = self._client_get().futures_ticker(symbol=symbol)
            if isinstance(tickers, list):
                if not tickers:
                    return None
                tickers = tickers[0]
            return float(tickers.get("quoteVolume", 0))
        except Exception as e:
            _log_reject("volume", symbol, f"24s hacim hatası: {e}")
            return None

    def passes_min_volume(self, symbol: str, source: str) -> bool:
        vol = self.get_24h_volume_usd(symbol)
        if vol is None:
            _log_reject(source, symbol, "24s hacim alınamadı")
            return False
        if vol < MIN_24H_VOLUME_USD:
            _log_reject(
                source,
                symbol,
                f"24s hacim {vol / 1e6:.1f}M < {MIN_24H_VOLUME_USD / 1e6:.0f}M USD",
            )
            return False
        return True

    def is_pumped_15m(self, symbol: str) -> bool:
        """Son 15 dakikada %5+ yükseliş varsa True (pump koruması)."""
        try:
            kl = self._client_get().futures_klines(symbol=symbol, interval="5m", limit=PUMP_LOOKBACK_5M + 2)
        except Exception as e:
            _log_reject(YUVA_EI, symbol, f"pump kontrol klines: {e}")
            return False
        closed = kl[:-1]
        if len(closed) < PUMP_LOOKBACK_5M + 1:
            return False
        ref = float(closed[-(PUMP_LOOKBACK_5M + 1)][4])
        now = float(closed[-1][4])
        if ref <= 0:
            return False
        change = (now - ref) / ref
        return change >= PUMP_15M_PCT

    def _extract_ei_long_symbols(self, text: str) -> List[str]:
        if "Yeni AL Sinyalleri" not in text:
            return []
        symbols: List[str] = []
        seen: set = set()
        for m in RE_EI_AL_SECTION.finditer(text):
            for sym in _extract_usdt_symbols(m.group(1)):
                if sym not in seen:
                    seen.add(sym)
                    symbols.append(sym)
        return symbols

    def _extract_rsi_entry(self, text: str) -> Optional[Dict[str, Any]]:
        if "RSI Analizi" not in text:
            return None
        for m in RE_RSI_ENTRY.finditer(text):
            zone = m.group(2)
            if "(<20)" not in zone:
                continue
            rsi_5 = _parse_num(m.group(3))
            return {
                "symbol": normalize_symbol(m.group(1)),
                "rsi_5m": rsi_5,
                "direction": "LONG",
            }
        return None

    def select_ei_symbol(self, text: str) -> Optional[Tuple[str, float]]:
        symbols = self._extract_ei_long_symbols(text)
        if not symbols:
            return None
        ranked: List[Tuple[str, float]] = []
        for sym in symbols:
            rvol = self.calculate_rvol(sym)
            if rvol is None:
                continue
            if rvol >= RVOL_MIN:
                if not self.passes_min_volume(sym, YUVA_EI):
                    continue
                ranked.append((sym, rvol))
            else:
                _log_reject(YUVA_EI, sym, f"RVOL {rvol:.2f} < {RVOL_MIN}")
        if not ranked:
            _log_reject(YUVA_EI, "—", "RVOL>=2.0 coin yok", {"candidates": len(symbols)})
            return None
        ranked.sort(key=lambda x: -x[1])
        for sym, rvol in ranked:
            if self.is_pumped_15m(sym):
                _log_reject(
                    YUVA_EI,
                    sym,
                    f"pump koruması: 15dk +{PUMP_15M_PCT * 100:.0f}% yükseliş, atlanıyor",
                    {"rvol": round(rvol, 2)},
                )
                continue
            _log(f"EI seçildi {sym} RVOL={rvol:.2f}")
            return sym, rvol
        _log_reject(YUVA_EI, "—", "RVOL geçen coinler pump filtresinde elendi")
        return None

    def check_rsi_signal(self, text: str) -> Optional[str]:
        entry = self._extract_rsi_entry(text)
        if not entry:
            return None
        sym = entry["symbol"]
        rsi_5 = entry.get("rsi_5m")
        if rsi_5 is None or rsi_5 >= RSI_OVERSOLD:
            _log_reject(YUVA_RSI, sym, f"RSI(5dk) {rsi_5} >= {RSI_OVERSOLD}")
            return None
        try:
            kl = self._client_get().futures_klines(symbol=sym, interval="5m", limit=50)
        except Exception as e:
            _log_reject(YUVA_RSI, sym, f"klines: {e}")
            return None
        closes = [float(k[4]) for k in kl[:-1]]
        if not _rsi_confirmation(closes):
            _log_reject(YUVA_RSI, sym, "RSI teyit yok (1-2 mum +3 veya 20 kırılım)")
            return None
        if not self.passes_min_volume(sym, YUVA_RSI):
            return None
        _log(f"RSI teyit OK {sym} rsi_5={rsi_5}")
        return sym

    def _yuva_busy(self, yuva: str) -> bool:
        return bool(self.state.get("positions", {}).get(yuva))

    def _double_confirm_parts(self, symbol: str, source: str) -> int:
        pending = self.state.setdefault("pending_confirm", {})
        other = YUVA_RSI if source == YUVA_EI else YUVA_EI
        p = pending.get(other)
        if p and p.get("symbol") == symbol:
            ts = p.get("at", "")
            try:
                t0 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - t0 <= timedelta(seconds=DOUBLE_CONFIRM_SEC):
                    pending.pop(other, None)
                    _log(f"ÇİFT TEYİT {symbol} — ilk giriş 2 parça")
                    return 2
            except Exception:
                pass
        pending[source] = {"symbol": symbol, "at": _now_iso()}
        self._save_state()
        return 1

    def _round_qty(self, symbol: str, qty: float) -> float:
        if symbol not in self._step_cache:
            info = self._client_get().futures_exchange_info()
            step = 0.001
            for s in info["symbols"]:
                if s["symbol"] == symbol:
                    for f in s.get("filters", []):
                        if f.get("filterType") == "LOT_SIZE":
                            step = float(f["stepSize"])
                    break
            self._step_cache[symbol] = step
        step = Decimal(str(self._step_cache[symbol]))
        q = Decimal(str(qty))
        if step > 0:
            return float((q / step).to_integral_value(rounding=ROUND_DOWN) * step)
        return float(q.quantize(Decimal("0.0001"), rounding=ROUND_DOWN))

    def _round_price(self, symbol: str, price: float) -> float:
        info = self._client_get().futures_exchange_info()
        tick = 0.01
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                for f in s.get("filters", []):
                    if f.get("filterType") == "PRICE_FILTER":
                        tick = float(f["tickSize"])
                break
        p = Decimal(str(price))
        t = Decimal(str(tick))
        if t > 0:
            return float((p / t).to_integral_value(rounding=ROUND_DOWN) * t)
        return round(price, 4)

    def _prepare_symbol(self, symbol: str) -> None:
        c = self._client_get()
        try:
            c.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        except Exception:
            pass
        try:
            c.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        except Exception:
            pass

    def _market_buy_parts(self, symbol: str, parts: int, mark: float) -> Tuple[float, float]:
        part_u = self.part_usdt()
        notional = part_u * parts
        qty = self._round_qty(symbol, notional / mark)
        if qty <= 0:
            raise ValueError(f"miktar sıfır symbol={symbol}")
        self._prepare_symbol(symbol)
        self._client_get().futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
            positionSide="LONG",
        )
        cost = qty * mark
        _log(f"MARKET {symbol} parts={parts} qty={qty} mark={mark:.6f} usdt≈{cost:.2f}")
        return qty, cost

    def _place_dca_limits(
        self,
        symbol: str,
        anchor: float,
        start_step: int,
        count: int,
    ) -> List[int]:
        """Limit alımlar: anchor * (1 - 0.02*n), n=start_step..start_step+count-1."""
        part_u = self.part_usdt()
        ids: List[int] = []
        for n in range(start_step, start_step + count):
            price = self._round_price(symbol, anchor * (1.0 - DCA_STEP * n))
            qty = self._round_qty(symbol, part_u / price)
            if qty <= 0:
                continue
            try:
                o = self._client_get().futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce="GTC",
                    quantity=qty,
                    price=price,
                    positionSide="LONG",
                )
                ids.append(int(o.get("orderId", 0)))
                _log(f"LIMIT DCA #{n} {symbol} price={price} qty={qty}")
            except Exception as e:
                _log(f"LIMIT hata {symbol} step={n}: {e}")
        return ids

    def open_dca_position(
        self,
        symbol: str,
        signal_source: str,
        initial_parts: int = 1,
    ) -> bool:
        if self._yuva_busy(signal_source):
            _log_reject(signal_source, symbol, "yuva dolu")
            return False
        if not self.passes_min_volume(symbol, signal_source):
            return False
        if initial_parts < 1 or initial_parts > PARTS_PER_YUVA:
            initial_parts = 1
        try:
            mark = float(self._client_get().futures_mark_price(symbol=symbol)["markPrice"])
        except Exception as e:
            _log_reject(signal_source, symbol, f"mark price: {e}")
            return False

        part_u = self.part_usdt()
        try:
            qty, cost = self._market_buy_parts(symbol, initial_parts, mark)
        except Exception as e:
            _log_reject(signal_source, symbol, f"market emir: {e}")
            return False

        limits_count = PARTS_PER_YUVA - initial_parts
        limit_ids = self._place_dca_limits(symbol, mark, 1, limits_count)

        journal = self._journal_get()
        trade_id = journal.log_trade_open(
            symbol=symbol,
            side="LONG",
            leverage=LEVERAGE,
            entry_price=mark,
            qty=qty,
            initial_margin=cost,
            signal_source=signal_source,
        )

        self.state.setdefault("positions", {})[signal_source] = {
            "symbol": symbol,
            "signal_source": signal_source,
            "trade_id": trade_id,
            "entry_anchor": mark,
            "parts_filled": initial_parts,
            "parts_total": PARTS_PER_YUVA,
            "total_qty": qty,
            "total_cost": cost,
            "avg_price": mark,
            "opened_at": _now_iso(),
            "tp1_done": False,
            "trailing_active": False,
            "trailing_peak": None,
            "breakeven_mode": False,
            "breakeven_since": None,
            "limit_order_ids": limit_ids,
            "part_usdt": part_u,
        }
        self.state.get("pending_confirm", {}).pop(signal_source, None)
        self._save_state()
        _log(f"AÇILDI {signal_source} {symbol} parts={initial_parts}/{PARTS_PER_YUVA} trade_id={trade_id}")
        return True

    def handle_message(self, text: str) -> bool:
        """EI veya RSI bot mesajını işle. Bot formatıysa True döner."""
        text = text.strip()
        if not text:
            return False

        if "Sinyal Taraması" in text or "Yeni AL Sinyalleri" in text:
            picked = self.select_ei_symbol(text)
            if not picked:
                return True
            sym, rvol = picked
            parts = self._double_confirm_parts(sym, YUVA_EI)
            self.open_dca_position(sym, YUVA_EI, initial_parts=parts)
            return True

        if "RSI Analizi" in text:
            sym = self.check_rsi_signal(text)
            if not sym:
                return True
            parts = self._double_confirm_parts(sym, YUVA_RSI)
            self.open_dca_position(sym, YUVA_RSI, initial_parts=parts)
            return True

        return False

    def monitor_positions(self) -> None:
        """TP / trailing / 48s timeout — periyodik çağrı."""
        positions = self.state.get("positions") or {}
        if not positions:
            return
        client = self._client_get()
        journal = self._journal_get()

        for yuva, pos in list(positions.items()):
            if not pos:
                continue
            symbol = pos["symbol"]
            try:
                mark = float(client.futures_mark_price(symbol=symbol)["markPrice"])
            except Exception:
                continue

            avg = float(pos.get("avg_price") or pos.get("entry_anchor"))
            qty = float(pos.get("total_qty") or 0)
            if qty <= 0 or avg <= 0:
                continue

            tp1 = avg * (1 + TP1_PCT)
            tp2 = avg * (1 + TP2_PCT)

            if not pos.get("tp1_done") and mark >= tp1:
                close_qty = self._round_qty(symbol, qty * 0.5)
                if close_qty > 0:
                    self._close_qty(symbol, close_qty, "TP1")
                    pos["total_qty"] = qty - close_qty
                    pos["tp1_done"] = True
                    self._save_state()
                continue

            if pos.get("tp1_done") and not pos.get("trailing_active") and mark >= tp2:
                pos["trailing_active"] = True
                pos["trailing_peak"] = mark
                _log(f"TP2 trailing aktif {symbol} peak={mark:.6f}")
                self._save_state()
                continue

            if pos.get("trailing_active") and pos.get("trailing_peak"):
                peak = float(pos["trailing_peak"])
                if mark > peak:
                    pos["trailing_peak"] = mark
                    peak = mark
                    self._save_state()
                trail_stop = peak * (1 - TRAIL_PCT)
                if mark <= trail_stop:
                    rem = float(pos.get("total_qty") or 0)
                    self._close_qty(symbol, rem, "Trailing")
                    self._finalize_close(yuva, pos, mark, journal, "Trailing")
                continue

            if pos.get("breakeven_mode") and mark >= avg:
                rem = float(pos.get("total_qty") or 0)
                if rem > 0:
                    self._close_qty(symbol, rem, "48h Breakeven")
                    self._finalize_close(yuva, pos, mark, journal, "48h Breakeven")
                continue

            opened = pos.get("opened_at", "")
            try:
                t0 = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - t0 >= timedelta(hours=MAX_HOLD_H):
                    if not pos.get("tp1_done") and not pos.get("breakeven_mode"):
                        pos["breakeven_mode"] = True
                        pos["breakeven_since"] = _now_iso()
                        _log(
                            f"48s timeout → breakeven modu {symbol} "
                            f"avg={avg:.6f} mark={mark:.6f} (maliyete gelince kapatılacak)"
                        )
                        self._save_state()
            except Exception:
                pass

    def _close_qty(self, symbol: str, qty: float, reason: str) -> None:
        qty = self._round_qty(symbol, qty)
        if qty <= 0:
            return
        self._client_get().futures_create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
            positionSide="LONG",
        )
        _log(f"KAPAT {symbol} qty={qty} reason={reason}")

    def _finalize_close(
        self,
        yuva: str,
        pos: Dict[str, Any],
        mark: float,
        journal: Any,
        reason: str,
    ) -> None:
        trade_id = pos.get("trade_id")
        qty = float(pos.get("total_qty") or 0)
        avg = float(pos.get("avg_price") or mark)
        pnl_usdt = (mark - avg) * qty
        pnl_pct = ((mark - avg) / avg) * 100 if avg else 0
        if trade_id and journal:
            journal.log_trade_close(
                trade_id=int(trade_id),
                close_price=mark,
                qty=qty,
                close_reason=reason,
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_pct,
                roe_percent=pnl_pct,
            )
        for oid in pos.get("limit_order_ids") or []:
            try:
                self._client_get().futures_cancel_order(symbol=pos["symbol"], orderId=oid)
            except Exception:
                pass
        self.state.get("positions", {}).pop(yuva, None)
        self._save_state()
        _log(f"TAM KAPANDI {yuva} {pos.get('symbol')} reason={reason}")
