# -*- coding: utf-8 -*-
"""
MİNA v2 - Tek Çekirdek Pozisyon Yöneticisi

Bu modül, eski backend/strategy_manager.py, backend/exit_system.py ve
backend/defense_system.py parçalarını tek bir çekirdekte birleştirmek için
sıfırdan oluşturulmuştur.

Kural seti, proje sahibi tarafından belirlenen "MINA Anayasası"na göre
oluşturulmuştur:
- Spot fiyat tetikleyicileri kullanılır.
- Defans tetikleyicilerinde ROE kullanılmaz.
- 4x için savunma sistemi ayrı bir süreç olarak değerlendirilir.
- TP ve stop-loss hesapları doğrudan giriş fiyatından türetilir.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional

from binance.client import Client
import mina_tracking as mt
from binance.enums import (
    FUTURE_ORDER_TYPE_STOP_MARKET,
    FUTURE_ORDER_TYPE_TRAILING_STOP_MARKET,
    ORDER_TYPE_MARKET,
    SIDE_BUY,
    SIDE_SELL,
)

ORDER_TYPE_STOP_MARKET = FUTURE_ORDER_TYPE_STOP_MARKET
ORDER_TYPE_TRAILING_STOP_MARKET = FUTURE_ORDER_TYPE_TRAILING_STOP_MARKET
ORDER_TYPE_TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"

D2_TIME_STOP_H = 8  # D2 sonrası TP/breakeven gelmezse tam kapama (saat)

try:
    from mina_trading_journal import TradingJournal
except ImportError:
    TradingJournal = None  # Journal modülü yok ise
    print("⚠️  Trading Journal modülü bulunamadı — logging devre dışı")


class MinaPositionManager:
    """Tek ve yalın pozisyon yönetim çekirdeği."""

    def __init__(
        self,
        client: Client,
        slot_size: float,
        journal: 'TradingJournal' = None,
        data_root: Optional[str] = None,
    ):
        self.client = client
        self.slot_size = slot_size
        self.data_root = data_root or mt.DATA_ROOT
        mt.DATA_ROOT = self.data_root
        self.position_states: Dict[str, Dict] = {}
        self.journal = journal  # Trading journal referansı
        self.trade_ids: Dict[str, int] = {}  # {pos_key: trade_id}
        self._lot_step_cache: Dict[str, float] = {}
        self._exchange_info_loaded: bool = False
        self._last_risk_level: str = "ok"

        self.leverage_rules = {
            1: {'stop_loss_pct': 3.0, 'tp_type': 'standard', 'has_defense': False},
            2: {'stop_loss_pct': 3.0, 'tp_type': 'standard', 'has_defense': False},
            3: {'stop_loss_pct': 2.0, 'tp_type': 'standard', 'has_defense': False},
            4: {'stop_loss_pct': None, 'tp_type': 'standard', 'has_defense': True},
            5: {'stop_loss_pct': 2.0, 'tp_type': 'standard', 'has_defense': False},
            6: {'stop_loss_pct': 2.0, 'tp_type': 'standard', 'has_defense': False},
            7: {'stop_loss_pct': 1.5, 'tp_type': 'standard', 'has_defense': False},
            8: {'stop_loss_pct': 1.0, 'tp_type': 'standard', 'has_defense': False},
            9: {'stop_loss_pct': 1.0, 'tp_type': 'standard', 'has_defense': False},
            10: {'stop_loss_pct': 1.0, 'tp_type': 'fast', 'has_defense': False},
        }

        self.tp_rules = {
            'standard': {
                'tp1_ratio': 0.50,
                'tp2_ratio': 0.50,
                'tp1_multiplier': 1.03,
                'tp2_multiplier': 1.05,
                'trailing_callback_pct': 2.0,
            },
            'fast': {
                'tp1_ratio': 0.50,
                'tp2_ratio': 1.00,
                'tp1_multiplier': 1.02,
                'tp2_multiplier': 1.04,
                'trailing_callback_pct': None,
            },
            'ht': {
                'stop_pct': 2.0,
                'tp1_rr': 2.0,
                'tp2_rr': 4.0,
                'trailing_callback_pct': None,
            },
        }

        self.defense_rules = {
            1: {'trigger_multiplier': 0.95, 'slot_ratio': 0.20},
            2: {'trigger_multiplier': 0.88, 'slot_ratio': 0.20},
            3: {'trigger_multiplier': 0.75, 'slot_ratio': 0.40},
        }

        self.state_file = os.path.join(self.data_root, 'mina_position_state.json')
        self._load_state()
        self._load_trade_ids_from_journal()

    def _rules_for_leverage(self, leverage: int) -> dict:
        """Kaldıraç kuralları — dashboard strateji ayarı ile birleştirilir."""
        base = dict(self.leverage_rules.get(leverage) or {})
        if leverage == 4:
            base['has_defense'] = True
            base['stop_loss_pct'] = None
            base['strategy_mode'] = 'defense'
            return base
        try:
            from mina_dashboard_settings import leverage_strategy_mode
            mode = leverage_strategy_mode(leverage)
        except ImportError:
            mode = 'defense'
        base['strategy_mode'] = mode
        if mode == 'full_manual':
            base['has_defense'] = False
            base['stop_loss_pct'] = None
            base['tp_type'] = 'full_manual'
            return base
        if mode == 'ht':
            base['has_defense'] = False
            base['stop_loss_pct'] = 2.0
            base['tp_type'] = 'ht'
            return base
        if mode == 'defense':
            base['has_defense'] = True
            base['stop_loss_pct'] = None
        else:
            base['has_defense'] = False
        return base

    # ---------------------------------------------------------------------
    # Binance ↔ disk senkronizasyonu
    # ---------------------------------------------------------------------

    @staticmethod
    def _pos_key(symbol: str, side: str) -> str:
        return mt.pos_key(symbol, side)

    def _get_initial_entry(self, symbol: str, side: str, fallback: float) -> float:
        prices = mt.load_json(mt.INITIAL_PRICE_FILE)
        return float(prices.get(self._pos_key(symbol, side), fallback))

    def _open_trade_from_journal(self, symbol: str, side: str) -> Optional[Dict[str, Any]]:
        """DERR'deki açık trade kaydı (sync / defense restore)."""
        if not self.journal:
            return None
        try:
            cursor = self.journal.conn.cursor()
            cursor.execute(
                """SELECT id, defense_triggered, weighted_avg_price, open_price
                   FROM trades WHERE symbol=? AND side=? AND status='open'
                   ORDER BY id DESC LIMIT 1""",
                (symbol, side),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def _defense_level_from_journal(self, symbol: str, side: str) -> int:
        row = self._open_trade_from_journal(symbol, side)
        if not row:
            return 0
        return int(row.get('defense_triggered') or 0)

    def sync_reality_from_binance(self, verbose: bool = True) -> Dict[str, Any]:
        """Açık pozisyonları Binance'ten okuyup tracking JSON + DERR ile hizalar."""
        from position_manager import PositionManager  # noqa: circular at module level

        pm = PositionManager(self.client)
        positions = pm.get_all_positions()
        report: Dict[str, Any] = {
            'open_count': len(positions),
            'synced_keys': [],
            'defense_preserved': [],
            'max_prices_seeded': [],
            'journal_opened': [],
        }

        initial_prices = mt.load_json(mt.INITIAL_PRICE_FILE)
        initial_margins = mt.load_json(mt.INITIAL_MARGIN_FILE)
        defense_levels = mt.load_json(mt.DEFENSE_FILE)
        tp_levels = mt.load_json(mt.TP_FILE)
        max_prices = mt.load_json(mt.MAX_PRICE_FILE)

        open_keys = set()
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            key = self._pos_key(symbol, side)
            open_keys.add(key)
            entry = float(pos['entry_price'])
            mark = float(pos.get('mark_price') or entry)
            margin = float(pos.get('isolated_margin') or 0)
            leverage = int(pos.get('leverage') or 4)

            old_entry = initial_prices.get(key)
            journal_row = self._open_trade_from_journal(symbol, side)
            preserved_defense = max(
                int(defense_levels.get(key, 0)),
                self._defense_level_from_journal(symbol, side),
            )

            if preserved_defense > 0 and old_entry is not None:
                initial_prices[key] = float(old_entry)
            elif journal_row and journal_row.get('open_price'):
                initial_prices[key] = float(journal_row['open_price'])
            else:
                initial_prices[key] = entry

            initial_margins[key] = round(margin, 4) if margin > 0 else round((entry * pos['amount']) / max(leverage, 1), 4)
            defense_levels[key] = preserved_defense
            if preserved_defense == 0:
                tp_levels[key] = 0
            if key not in max_prices:
                max_prices[key] = mark

            report['synced_keys'].append({
                'key': key,
                'old_initial_entry': old_entry,
                'new_initial_entry': initial_prices[key],
                'mark': mark,
                'defense_level': preserved_defense,
                'd1_long': round(float(initial_prices[key]) * 0.95, 8) if side == 'LONG' else round(float(initial_prices[key]) / 0.95, 8),
                'd2_long': round(float(initial_prices[key]) * 0.88, 8) if side == 'LONG' else round(float(initial_prices[key]) / 1.12, 8),
            })
            report['defense_preserved'].append({'key': key, 'level': preserved_defense})
            report['max_prices_seeded'].append({key: max_prices.get(key, mark)})

            self.init_position_state(symbol, entry, side=side)
            state = self.position_states.get(symbol, {})
            state['defense_stage'] = max(int(state.get('defense_stage', 0)), preserved_defense)
            state['highest_price'] = mark
            if preserved_defense > 0 and journal_row and journal_row.get('weighted_avg_price'):
                state['weighted_avg_price'] = float(journal_row['weighted_avg_price'])
            if preserved_defense >= 2:
                state['tp_disabled'] = True
            if preserved_defense >= 2 and state.get('d2_triggered_at') is None:
                state['d2_triggered_at'] = time.time()
            self._save_state()

            if self.journal:
                cursor = self.journal.conn.cursor()
                cursor.execute(
                    "SELECT id FROM trades WHERE symbol=? AND side=? AND status='open' ORDER BY id DESC LIMIT 1",
                    (symbol, side),
                )
                row = cursor.fetchone()
                if row:
                    tid = int(row['id'])
                    self.trade_ids[key] = tid
                else:
                    from mina_signal_source import detect_orphan_signal_source, record_position_source
                    orphan_src = detect_orphan_signal_source(symbol, side)
                    record_position_source(symbol, side, orphan_src)
                    tid = self.journal.log_trade_open(
                        symbol=symbol,
                        side=side,
                        leverage=leverage,
                        entry_price=entry,
                        qty=float(pos['amount']),
                        initial_margin=initial_margins[key],
                        signal_source=orphan_src,
                    )
                    if tid > 0:
                        self.trade_ids[key] = tid
                        report['journal_opened'].append({'key': key, 'trade_id': tid, 'signal_source': orphan_src})

                if tid > 0 and preserved_defense > self._defense_level_from_journal(symbol, side):
                    st = self.position_states.get(symbol, {})
                    entry_ref = float(initial_prices[key])
                    defense_prices = {
                        'D1': entry_ref * 0.95,
                        'D2': entry_ref * 0.88,
                        'D3': entry_ref * 0.75,
                    }
                    weighted_avg = float(st.get('weighted_avg_price') or entry)
                    self.journal.log_defense_triggered(
                        trade_id=tid,
                        defense_level=preserved_defense,
                        defense_prices=defense_prices,
                        weighted_avg=weighted_avg,
                    )
                    if verbose:
                        print(f"[SYNC] journal defense backfill: {key} D{preserved_defense} id={tid}")

            if verbose:
                print(f"[SYNC] {key} entry={entry} mark={mark} margin={initial_margins[key]}")

        all_tracked = (
            set(initial_prices) | set(initial_margins) | set(defense_levels)
            | set(tp_levels) | set(max_prices)
        )
        stale = all_tracked - open_keys
        for key in stale:
            for d in (initial_prices, initial_margins, defense_levels, tp_levels, max_prices):
                d.pop(key, None)
            if verbose:
                print(f"[SYNC] stale removed: {key}")

        mt.save_json(mt.INITIAL_PRICE_FILE, initial_prices)
        mt.save_json(mt.INITIAL_MARGIN_FILE, initial_margins)
        mt.save_json(mt.DEFENSE_FILE, defense_levels)
        mt.save_json(mt.TP_FILE, tp_levels)
        mt.save_json(mt.MAX_PRICE_FILE, max_prices)
        self._save_state()
        try:
            from mina_manual_override import clear_stale
            cleared = clear_stale(open_keys, self.data_root)
            if cleared and verbose:
                print(f"[SYNC] manual_override cleared: {cleared} stale")
        except ImportError:
            pass

        reconciled = self.reconcile_journal_closed(open_keys)
        if reconciled:
            report['journal_reconciled'] = reconciled
            if verbose:
                for r in reconciled:
                    print(f"[SYNC] journal closed (reconcile): {r['key']} id={r['trade_id']} reason={r['reason']}")

        return report

    def reconcile_journal_closed(self, open_keys: set) -> List[Dict[str, Any]]:
        """Binance'te kapalı ama DERR'de hâlâ open olan kayıtları kapat."""
        if not self.journal:
            return []

        closed_report: List[Dict[str, Any]] = []
        try:
            cursor = self.journal.conn.cursor()
            cursor.execute(
                """SELECT id, symbol, side, open_price, open_qty, initial_margin
                   FROM trades WHERE status = 'open'"""
            )
            rows = cursor.fetchall()

            for row in rows:
                symbol = row['symbol']
                side = row['side']
                key = self._pos_key(symbol, side)
                if key in open_keys:
                    continue

                trade_id = int(row['id'])
                entry_price = float(row['open_price'])
                qty = float(row['open_qty'])
                init_margin = float(row['initial_margin'] or 1)

                try:
                    ticker = self.client.futures_mark_price(symbol=symbol)
                    close_price = float(ticker['markPrice'])
                except Exception:
                    close_price = entry_price

                if side == 'LONG':
                    pnl_usdt = (close_price - entry_price) * qty
                else:
                    pnl_usdt = (entry_price - close_price) * qty
                notional = entry_price * qty if entry_price > 0 else 1
                pnl_percent = (pnl_usdt / notional) * 100
                roe_percent = (pnl_usdt / init_margin) * 100 if init_margin > 0 else 0

                self.journal.log_trade_close(
                    trade_id=trade_id,
                    close_price=close_price,
                    qty=qty,
                    close_reason='Reconciliation',
                    pnl_usdt=pnl_usdt,
                    pnl_percent=pnl_percent,
                    roe_percent=roe_percent,
                )
                self.trade_ids.pop(key, None)
                closed_report.append({
                    'key': key,
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'side': side,
                    'reason': 'Reconciliation',
                    'close_price': close_price,
                    'pnl_usdt': round(pnl_usdt, 4),
                })
        except Exception as e:
            print(f"❌ Journal reconcile hatası: {e}")

        if closed_report:
            self._save_state()
        return closed_report

    def get_binance_open_keys(self) -> set:
        """Binance'teki gerçek açık pozisyon anahtarları (DERR değil)."""
        from position_manager import PositionManager

        pm = PositionManager(self.client)
        positions = pm.get_all_positions()
        return {self._pos_key(p['symbol'], p['side']) for p in positions}

    def reconcile_derr_with_binance(self, verbose: bool = False) -> List[Dict[str, Any]]:
        """Binance'te kapalı, DERR'de açık kalan kayıtları Reconciliation ile kapat."""
        open_keys = self.get_binance_open_keys()
        reconciled = self.reconcile_journal_closed(open_keys)
        if verbose and reconciled:
            for r in reconciled:
                print(
                    f"[RECONCILE] id={r['trade_id']} {r['key']} "
                    f"pnl={r.get('pnl_usdt')} reason={r.get('reason')}"
                )
        return reconciled

    def _load_trade_ids_from_journal(self) -> None:
        if not self.journal:
            return
        try:
            cursor = self.journal.conn.cursor()
            cursor.execute(
                "SELECT id, symbol, side FROM trades WHERE status='open'"
            )
            for row in cursor.fetchall():
                key = self._pos_key(row['symbol'], row['side'])
                self.trade_ids[key] = int(row['id'])
        except Exception:
            pass

    def _persist_defense_level(self, symbol: str, side: str, level: int) -> None:
        data = mt.load_json(mt.DEFENSE_FILE)
        key = self._pos_key(symbol, side)
        data[key] = max(int(data.get(key, 0)), int(level))
        mt.save_json(mt.DEFENSE_FILE, data)

    def _persist_tp_level(self, symbol: str, side: str, level: int) -> None:
        data = mt.load_json(mt.TP_FILE)
        data[self._pos_key(symbol, side)] = level
        mt.save_json(mt.TP_FILE, data)

    def _update_max_price(self, symbol: str, side: str, current_price: float) -> float:
        key = self._pos_key(symbol, side)
        max_prices = mt.load_json(mt.MAX_PRICE_FILE)
        if key not in max_prices:
            max_prices[key] = current_price
        peak = float(max_prices[key])
        if side == 'LONG' and current_price > peak:
            peak = current_price
            max_prices[key] = peak
        elif side == 'SHORT' and current_price < peak:
            peak = current_price
            max_prices[key] = peak
        mt.save_json(mt.MAX_PRICE_FILE, max_prices)
        return peak

    # ---------------------------------------------------------------------
    # State management
    # ---------------------------------------------------------------------

    def _load_state(self) -> None:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.position_states = json.load(f)
            except Exception:
                self.position_states = {}

    def _save_state(self) -> None:
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.position_states, f, indent=2)
        except Exception:
            pass

    def _file_defense_stage(self, symbol: str, side: Optional[str] = None) -> int:
        dl = mt.load_json(mt.DEFENSE_FILE)
        if side:
            return int(dl.get(self._pos_key(symbol, side), 0))
        return max(
            int(dl.get(self._pos_key(symbol, 'LONG'), 0)),
            int(dl.get(self._pos_key(symbol, 'SHORT'), 0)),
            0,
        )

    def init_position_state(
        self, symbol: str, entry_price: float, side: Optional[str] = None
    ) -> None:
        """Yeni pozisyon için başlangıç state'i oluşturur (mevcut savunma korunur)."""
        existing = self.position_states.get(symbol, {})
        preserved_defense = max(
            int(existing.get('defense_stage', 0)),
            self._file_defense_stage(symbol, side),
        )
        self.position_states[symbol] = {
            'entry_price': entry_price,
            'tp1_done': bool(existing.get('tp1_done', False)),
            'tp2_done': bool(existing.get('tp2_done', False)),
            'highest_price': existing.get('highest_price', entry_price),
            'defense_stage': preserved_defense,
            'd2_order_active': bool(existing.get('d2_order_active', False)),
            'd2_order_id': existing.get('d2_order_id'),
            'd3_order_id': existing.get('d3_order_id'),
            'tp_disabled': bool(existing.get('tp_disabled', False) or preserved_defense >= 2),
            'weighted_avg_price': existing.get('weighted_avg_price', entry_price),
            'd2_triggered_at': existing.get('d2_triggered_at'),
        }
        self._save_state()

    def reset_position_state(self, symbol: str) -> None:
        if symbol in self.position_states:
            del self.position_states[symbol]
            self._save_state()
        try:
            from mina_manual_override import clear_override
            for side in ('LONG', 'SHORT'):
                clear_override(self._pos_key(symbol, side), self.data_root)
        except ImportError:
            pass

    # ---------------------------------------------------------------------
    # Günlük zarar limiti / kill-switch
    # ---------------------------------------------------------------------

    def _get_futures_usdt_balance(self) -> float:
        try:
            for asset in self.client.futures_account_balance():
                if asset.get("asset") == "USDT":
                    return float(asset.get("balance", 0))
        except Exception as e:
            print(f"   ⚠️  Bakiye okunamadı (risk limiti): {e}")
        return 0.0

    def _send_risk_telegram(self, message: str) -> None:
        try:
            from tools.telegram_bot import send_notification
            send_notification(message)
        except Exception as e:
            print(f"   ⚠️  Risk Telegram hatası: {e}")

    def check_daily_risk_limit(self) -> Dict[str, Any]:
        """DERR bugünkü realize PnL vs dinamik günlük zarar limiti."""
        from mina_dashboard_settings import (
            daily_loss_limit_pct,
            load_daily_risk_state,
            save_daily_risk_state,
            set_daily_loss_kill,
            is_daily_loss_kill_active,
        )

        today = date.today().isoformat()
        state = load_daily_risk_state()
        if state.get("date") != today:
            state = {"date": today, "half_alert_sent": False, "kill_alert_sent": False}
            set_daily_loss_kill(False)

        balance = self._get_futures_usdt_balance()
        limit_pct = daily_loss_limit_pct()
        limit_usdt = -(balance * limit_pct / 100.0)
        half_usdt = limit_usdt / 2.0

        today_pnl = 0.0
        if self.journal is not None:
            today_pnl = self.journal.get_today_realized_pnl()

        level = "ok"
        if today_pnl <= limit_usdt:
            level = "kill"
        elif today_pnl <= half_usdt:
            level = "warn"

        if level == "warn" and not state.get("half_alert_sent"):
            self._send_risk_telegram(
                f"⚠️ Uyarı: Günlük zarar %{limit_pct / 2:.0f}'e ulaştı\n"
                f"Bugünkü PnL: {today_pnl:+.2f} USDT | Limit: {limit_usdt:.2f} USDT"
            )
            state["half_alert_sent"] = True
            print(f"   ⚠️  Günlük zarar yarı limit: {today_pnl:.2f} / {half_usdt:.2f} USDT")

        if level == "kill":
            set_daily_loss_kill(True)
            if not state.get("kill_alert_sent"):
                closed = 0
                if not state.get("positions_closed_on_kill"):
                    closed = self._close_all_positions_for_kill()
                    state["positions_closed_on_kill"] = True
                self._send_risk_telegram(
                    "🚨 KRİTİK: Günlük zarar limiti aşıldı!\n"
                    f"Bugünkü PnL: {today_pnl:+.2f} USDT | Limit: {limit_usdt:.2f} USDT\n"
                    f"Tüm pozisyonlar kapatıldı ({closed} adet). Motor durduruldu."
                )
                state["kill_alert_sent"] = True
                print(
                    f"   🚨 Günlük zarar kill-switch: {today_pnl:.2f} <= {limit_usdt:.2f} USDT "
                    f"— {closed} pozisyon kapatıldı"
                )
        elif is_daily_loss_kill_active() and today_pnl > limit_usdt:
            set_daily_loss_kill(False)
            state["positions_closed_on_kill"] = False

        state.update(
            {
                "date": today,
                "today_pnl": round(today_pnl, 2),
                "balance": round(balance, 2),
                "limit_pct": limit_pct,
                "limit_usdt": round(limit_usdt, 2),
                "half_usdt": round(half_usdt, 2),
                "level": level,
                "new_entries_blocked": level == "kill",
            }
        )
        save_daily_risk_state(state)
        self._last_risk_level = level
        return state

    def _close_all_positions_for_kill(self) -> int:
        """Kill-switch: tüm açık pozisyonları MARKET ile kapat."""
        closed = 0
        try:
            for p in self.client.futures_position_information():
                amt = float(p.get("positionAmt") or 0)
                if amt == 0:
                    continue
                sym = p["symbol"]
                side = "LONG" if amt > 0 else "SHORT"
                order_side = SIDE_SELL if amt > 0 else SIDE_BUY
                qty = self._round_quantity(abs(amt), sym)
                if qty <= 0:
                    continue
                order = self._futures_create_order(
                    label="Daily Kill",
                    symbol=sym,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=qty,
                    positionSide=side,
                )
                if order:
                    closed += 1
                    print(f"   🚨 Kill-switch kapama: {sym} {side} qty={qty}")
        except Exception as e:
            print(f"   ❌ Kill-switch toplu kapama hatası: {e}")
        return closed

    def is_new_entry_allowed(self) -> bool:
        return self._last_risk_level != "kill"

    # ---------------------------------------------------------------------
    # D2/D3 emir doğrulama (testnet -4120 → LIMIT fallback)
    # ---------------------------------------------------------------------

    @staticmethod
    def _order_error_code(exc: BaseException) -> Optional[int]:
        code = getattr(exc, "code", None)
        if code is not None:
            try:
                return int(code)
            except (TypeError, ValueError):
                pass
        msg = str(exc)
        if "-4120" in msg or "4120" in msg:
            return -4120
        return None

    def _notify_defense_order_failure(self, label: str, symbol: str, side: str, error: str) -> None:
        print(f"   ❌ {label} emri başarısız: {symbol} {side} — {error}")
        self._send_risk_telegram(
            f"⚠️ *{label} emri başarısız*\n{symbol} {side}\n`{error}`"
        )

    def _verify_exchange_order(self, symbol: str, order_id: Optional[int]) -> bool:
        if not order_id:
            return False
        try:
            order = self.client.futures_get_order(symbol=symbol, orderId=int(order_id))
            status = str(order.get("status", "")).upper()
            return status in ("NEW", "PARTIALLY_FILLED", "FILLED")
        except Exception as e:
            print(f"   ⚠️  Emir doğrulama hatası {symbol} #{order_id}: {e}")
            return False

    def _verify_market_add(self, symbol: str, side: str, order: Dict) -> bool:
        order_id = order.get("orderId")
        if order_id and self._verify_exchange_order(symbol, order_id):
            return True
        status = str(order.get("status", "")).upper()
        if status == "FILLED":
            return True
        try:
            for p in self.client.futures_position_information(symbol=symbol):
                amt = float(p.get("positionAmt", 0))
                if p.get("positionSide") == side and amt != 0:
                    return True
        except Exception:
            pass
        return False

    def _place_breakeven_escape_order(
        self,
        symbol: str,
        side: str,
        breakeven_price: float,
        quantity: float,
        label: str,
    ) -> Optional[Dict]:
        """D2/D3 kaçış emri — mainnet TAKE_PROFIT_MARKET, testnet -4120 → LIMIT GTC."""
        escape_side = SIDE_SELL if side == "LONG" else SIDE_BUY
        qty = self._round_quantity(quantity, symbol)
        stop_px = self._round_price(breakeven_price, symbol)
        try:
            mark = float(self.client.futures_mark_price(symbol=symbol)["markPrice"])
            if side == "LONG" and stop_px < mark:
                stop_px = self._round_price(mark * 1.001, symbol)
            elif side == "SHORT" and stop_px > mark:
                stop_px = self._round_price(mark * 0.999, symbol)
        except Exception:
            pass
        order: Optional[Dict] = None
        order_type = ORDER_TYPE_TAKE_PROFIT_MARKET

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=escape_side,
                type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=stop_px,
                quantity=qty,
                positionSide=side,
                workingType="MARK_PRICE",
            )
        except Exception as e1:
            if self._order_error_code(e1) != -4120:
                self._notify_defense_order_failure(label, symbol, side, str(e1))
                return None
            print(f"   ⚠️  {label}: TAKE_PROFIT_MARKET -4120 → LIMIT GTC fallback ({symbol})")
            try:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=escape_side,
                    type="LIMIT",
                    price=stop_px,
                    quantity=qty,
                    timeInForce="GTC",
                    positionSide=side,
                )
                order_type = "LIMIT"
            except Exception as e2:
                self._notify_defense_order_failure(label, symbol, side, str(e2))
                return None

        order_id = order.get("orderId") if order else None
        if not self._verify_exchange_order(symbol, order_id):
            self._notify_defense_order_failure(
                label, symbol, side, f"Emir borsada doğrulanamadı orderId={order_id}"
            )
            return None

        print(f"   ✅ {label} kaçış emri doğrulandı: {order_type} orderId={order_id} @{stop_px}")
        if order is not None:
            order["_mina_order_type"] = order_type
        return order

    # ---------------------------------------------------------------------
    # Public decision API
    # ---------------------------------------------------------------------

    def evaluate_position(self, position: Dict, current_price: float) -> Dict:
        """Pozisyona göre bir aksiyon döndürür."""
        leverage = position.get('leverage')
        symbol = position.get('symbol')
        side = position.get('side')
        entry_price = position.get('entry_price')

        try:
            from ghost_positions import is_merter_dca_position, is_upbit_listing_managed
            if is_merter_dca_position(symbol, side, leverage):
                return {'action': 'hold', 'reason': 'Merter DCA yönetiminde'}
            if is_upbit_listing_managed(symbol, side):
                return {'action': 'hold', 'reason': 'Upbit listing trader yönetiminde'}
        except ImportError:
            pass

        key = self._pos_key(symbol, side)
        try:
            from mina_manual_override import get_override
            ov = get_override(key, self.data_root)
            if ov.get('active'):
                stop_px = ov.get('stop')
                tp_px = ov.get('tp')
                if side == 'LONG':
                    if stop_px is not None and current_price <= float(stop_px):
                        return {
                            'action': 'manual_stop',
                            'reason': f'Manuel stop tetiklendi ({stop_px})',
                        }
                    if tp_px is not None and current_price >= float(tp_px):
                        return {
                            'action': 'manual_tp',
                            'reason': f'Manuel TP tetiklendi ({tp_px})',
                        }
                else:
                    if stop_px is not None and current_price >= float(stop_px):
                        return {
                            'action': 'manual_stop',
                            'reason': f'Manuel stop tetiklendi ({stop_px})',
                        }
                    if tp_px is not None and current_price <= float(tp_px):
                        return {
                            'action': 'manual_tp',
                            'reason': f'Manuel TP tetiklendi ({tp_px})',
                        }
                return {'action': 'hold', 'reason': 'Manuel yönetim modu aktif'}
        except ImportError:
            pass

        rules = self._rules_for_leverage(leverage)
        if not rules:
            return {'action': 'hold', 'reason': f'Bilinmeyen kaldıraç: {leverage}x'}

        if rules.get('strategy_mode') == 'full_manual':
            return {'action': 'hold', 'reason': 'Full Manuel mod — motor müdahale etmez'}

        state = self.position_states.get(symbol)
        if state is None:
            self.init_position_state(symbol, entry_price, side=side)
            state = self.position_states[symbol]

        if rules['has_defense']:
            key = self._pos_key(symbol, side)
            file_defense = int(mt.load_json(mt.DEFENSE_FILE).get(key, 0))
            journal_defense = self._defense_level_from_journal(symbol, side)
            defense_stage = max(
                int(state.get('defense_stage', 0)),
                file_defense,
                journal_defense,
            )
            if defense_stage >= 2 and self._should_d2_time_stop(state):
                return {
                    'action': 'd2_time_stop',
                    'reason': f'D2 {D2_TIME_STOP_H}h zaman stopu — TP/breakeven gelmedi',
                }

            if defense_stage > int(state.get('defense_stage', 0)):
                state['defense_stage'] = defense_stage
                if defense_stage >= 2:
                    state['tp_disabled'] = True
                self._save_state()

            defense_level = self.check_spot_defense_trigger(position, current_price)
            # Idempotency: dosya/state/journal zaten bu seviyede veya üstündeyse tekrar tetikleme
            if defense_level > 0 and defense_level <= defense_stage:
                defense_level = 0
            if defense_level > 0:
                return {
                    'action': 'defense',
                    'defense_level': defense_level,
                    'reason': f'D{defense_level} spot fiyat tetiklendi'
                }

        tp_type = rules.get('tp_type') or self._get_tp_type(position)
        if tp_type == 'ht':
            stop_price = self._calculate_ht_stop_price(position, state)
            if stop_price is not None and self._is_stop_loss_hit(current_price, stop_price, side):
                label = 'HT breakeven stop' if state.get('tp1_done') else 'HT stop (%2)'
                return {
                    'action': 'stop_loss',
                    'reason': f'{label} tetiklendi ({stop_price})',
                }
        elif rules.get('stop_loss_pct') is not None:
            stop_price = self.calculate_stop_loss_price(entry_price, leverage, side)
            if self._is_stop_loss_hit(current_price, stop_price, side):
                return {
                    'action': 'stop_loss',
                    'reason': f'Stop-loss fiyatı aşıldı ({stop_price})',
                }

        tp_rules = self.tp_rules.get(tp_type) or self.tp_rules['standard']

        tp_action = self.check_take_profit(position, current_price, tp_rules)
        if tp_action is not None:
            return tp_action

        trailing_action = self.check_trailing_stop(position, current_price, tp_rules)
        if trailing_action is not None:
            return trailing_action

        return {'action': 'hold', 'reason': 'Pozisyon izleniyor'}

    def execute_action(self, position: Dict, action: Dict, current_price: float) -> bool:
        """Belirlenen aksiyonu uygular."""
        action_type = action.get('action')

        if action_type == 'defense':
            return self.execute_defense_action(position, action['defense_level'], current_price)
        if action_type == 'd2_time_stop':
            return self.execute_d2_time_stop(position, current_price)
        if action_type == 'stop_loss':
            return self.execute_stop_loss(position)
        if action_type == 'take_profit':
            return self.execute_take_profit(position, action['level'])
        if action_type == 'trailing_stop':
            return self.execute_trailing_stop(position)
        if action_type == 'manual_stop':
            return self.execute_manual_close(position, current_price, 'Manuel Stop')
        if action_type == 'manual_tp':
            return self.execute_manual_close(position, current_price, 'Manuel TP')

        return False

    # ---------------------------------------------------------------------
    # TP / trailing helpers
    # ---------------------------------------------------------------------

    def calculate_tp_price(self, entry_price: float, level: int, tp_type: str) -> float:
        if tp_type == 'ht':
            return self._calculate_ht_tp_price(entry_price, level, 'LONG')
        key = 'tp1_multiplier' if level == 1 else 'tp2_multiplier'
        return entry_price * self.tp_rules[tp_type][key]

    def _calculate_ht_tp_price(self, entry_price: float, level: int, side: str) -> float:
        ht = self.tp_rules['ht']
        dist = ht['stop_pct'] / 100.0
        rr = ht['tp1_rr'] if level == 1 else ht['tp2_rr']
        if side == 'LONG':
            return entry_price * (1 + dist * rr)
        return entry_price * (1 - dist * rr)

    def _calculate_ht_stop_price(self, position: Dict, state: Dict) -> Optional[float]:
        side = position.get('side')
        entry = self._get_effective_entry_price(position)
        if not entry:
            return None
        if state.get('tp1_done'):
            return float(entry)
        dist = self.tp_rules['ht']['stop_pct'] / 100.0
        if side == 'LONG':
            return entry * (1 - dist)
        return entry * (1 + dist)

    def check_take_profit(self, position: Dict, current_price: float, tp_rules: Dict) -> Optional[Dict]:
        symbol = position.get('symbol')
        side = position.get('side')
        state = self.position_states.get(symbol, {})
        tp_type = self._get_tp_type(position)

        if state.get('tp_disabled'):
            return None

        effective_entry = self._get_effective_entry_price(position)

        if tp_type == 'ht':
            if not state.get('tp1_done'):
                tp1_price = self._calculate_ht_tp_price(effective_entry, 1, side)
                if self._is_tp_hit(current_price, tp1_price, side):
                    return {'action': 'take_profit', 'level': 1, 'reason': 'HT TP1 (1:2 R/R) tetiklendi'}
            elif not state.get('tp2_done'):
                tp2_price = self._calculate_ht_tp_price(effective_entry, 2, side)
                if self._is_tp_hit(current_price, tp2_price, side):
                    return {'action': 'take_profit', 'level': 2, 'reason': 'HT TP2 (1:4 R/R) tetiklendi'}
            return None

        if not state.get('tp1_done'):
            tp1_price = self.calculate_tp_price(effective_entry, 1, self._get_tp_type(position))
            if self._is_tp_hit(current_price, tp1_price, side):
                return {'action': 'take_profit', 'level': 1, 'reason': 'TP1 spot fiyat tetiklendi'}

        if state.get('tp1_done') and not state.get('tp2_done'):
            tp2_price = self.calculate_tp_price(effective_entry, 2, self._get_tp_type(position))
            if self._is_tp_hit(current_price, tp2_price, side):
                return {'action': 'take_profit', 'level': 2, 'reason': 'TP2 spot fiyat tetiklendi'}

        return None

    def check_trailing_stop(self, position: Dict, current_price: float, tp_rules: Dict) -> Optional[Dict]:
        tp_type = self._get_tp_type(position)
        if tp_type in ('ht', 'full_manual'):
            return None
        symbol = position.get('symbol')
        side = position.get('side')
        state = self.position_states.get(symbol, {})
        tp_level = mt.load_json(mt.TP_FILE).get(self._pos_key(symbol, side), 0)

        if tp_level < 2 and not state.get('tp2_done'):
            return None
        if state.get('trailing_order_active'):
            return None

        peak = self._update_max_price(symbol, side, current_price)
        callback = tp_rules.get('trailing_callback_pct')
        if callback is None:
            callback = 2.0

        if side == 'LONG':
            drawdown = (peak - current_price) / peak * 100 if peak else 0
            if drawdown >= callback:
                return {
                    'action': 'trailing_stop',
                    'reason': f'Trailing (max_prices) peak={peak:.4f} now={current_price:.4f} dd={drawdown:.2f}%',
                }
        else:
            drawup = (current_price - peak) / peak * 100 if peak else 0
            if drawup >= callback:
                return {
                    'action': 'trailing_stop',
                    'reason': f'Trailing (max_prices) trough={peak:.4f} now={current_price:.4f} up={drawup:.2f}%',
                }

        return None

    # ---------------------------------------------------------------------
    # Stop-loss helpers
    # ---------------------------------------------------------------------

    def calculate_stop_loss_price(self, entry_price: float, leverage: int, side: str) -> float:
        rules = self._rules_for_leverage(leverage)
        pct = rules.get('stop_loss_pct') or 0.0
        if side == 'LONG':
            return entry_price * (1 - pct / 100)
        return entry_price * (1 + pct / 100)

    def _is_stop_loss_hit(self, current_price: float, stop_price: float, side: str) -> bool:
        if side == 'LONG':
            return current_price <= stop_price
        return current_price >= stop_price

    # ---------------------------------------------------------------------
    # Defense helpers
    # ---------------------------------------------------------------------

    def check_spot_defense_trigger(self, position: Dict, current_price: float) -> int:
        symbol = position.get('symbol')
        side = position.get('side')
        entry_price = self._get_initial_entry(
            symbol, side, float(position.get('entry_price', 0))
        )
        state = self.position_states.get(symbol, {})
        file_defense = int(mt.load_json(mt.DEFENSE_FILE).get(self._pos_key(symbol, side), 0))
        journal_defense = self._defense_level_from_journal(symbol, side)
        state_stage = int(state.get('defense_stage', 0))
        # D1 idempotency: dosya, state veya DERR'de >=1 ise D1 tekrar tetiklenmez
        current_stage = max(journal_defense, state_stage, file_defense)

        if current_stage == 0 and self._is_d1_hit(current_price, entry_price, side):
            return 1
        if current_stage <= 1 and self._is_d2_hit(current_price, entry_price, side):
            return 2
        if current_stage <= 2 and self._is_d3_hit(current_price, entry_price, side) and self._check_d3_sfp(symbol, side):
            return 3
        if self._is_hard_stop_hit(current_price, entry_price, side):
            return 99

        return 0

    def _is_d1_hit(self, current_price: float, entry_price: float, side: str) -> bool:
        if side == 'LONG':
            return current_price <= entry_price * self.defense_rules[1]['trigger_multiplier']
        return current_price >= entry_price / self.defense_rules[1]['trigger_multiplier']

    def _is_d2_hit(self, current_price: float, entry_price: float, side: str) -> bool:
        if side == 'LONG':
            return current_price <= entry_price * self.defense_rules[2]['trigger_multiplier']
        return current_price >= entry_price / self.defense_rules[2]['trigger_multiplier']

    def _is_d3_hit(self, current_price: float, entry_price: float, side: str) -> bool:
        if side == 'LONG':
            return current_price <= entry_price * self.defense_rules[3]['trigger_multiplier']
        return current_price >= entry_price / self.defense_rules[3]['trigger_multiplier']

    def _is_hard_stop_hit(self, current_price: float, entry_price: float, side: str) -> bool:
        hard_stop_multiplier = 0.75
        if side == 'LONG':
            return current_price <= entry_price * hard_stop_multiplier
        return current_price >= entry_price / hard_stop_multiplier

    def execute_defense_action(self, position: Dict, defense_level: int, current_price: float) -> bool:
        symbol = position.get('symbol')
        side = position.get('side')
        state = self.position_states.get(symbol)

        if not state:
            return False

        if defense_level == 99:
            return self.execute_hard_stop(position)

        if defense_level == 1:
            ok = self._execute_d1(position, current_price)
            if ok:
                cur = int(mt.load_json(mt.DEFENSE_FILE).get(self._pos_key(symbol, side), 0))
                if cur < 1:
                    self._persist_defense_level(symbol, side, 1)
            return ok

        state['defense_stage'] = defense_level
        self._save_state()
        self._persist_defense_level(symbol, side, defense_level)

        if defense_level == 2:
            return self._execute_d2(position, current_price)
        if defense_level == 3:
            return self._execute_d3(position, current_price)

        return False

    def _execute_d1(self, position: Dict, current_price: float) -> bool:
        symbol = position.get('symbol')
        side = position.get('side')
        amount = float(position.get('amount', 0.0))
        state = self.position_states.get(symbol)

        if not state or amount <= 0:
            return False

        key = self._pos_key(symbol, side)
        file_defense = int(mt.load_json(mt.DEFENSE_FILE).get(key, 0))
        stage = int(state.get('defense_stage', 0))
        journal_defense = self._defense_level_from_journal(symbol, side)
        already_d1 = max(stage, file_defense, journal_defense) >= 1
        if already_d1:
            state['defense_stage'] = max(stage, file_defense, journal_defense, 1)
            self._save_state()
            if file_defense < 1:
                self._persist_defense_level(symbol, side, 1)
            target = int(state['defense_stage'])
            self._backfill_journal_defense_if_needed(symbol, side, position, target)
            print(f"   ⏭️  D1 atlandı (idempotent): {symbol} stage={state['defense_stage']}")
            return True

        add_usdt = self.slot_size / 5
        add_qty = self._round_quantity(add_usdt / current_price, symbol)
        if add_qty <= 0:
            return False

        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        try:
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=add_qty,
                positionSide=side
            )
        except Exception as e:
            print(f"   ❌ D1 ekleme hatası: {e}")
            return False

        total_qty = amount + add_qty
        weighted_avg = ((amount * float(position.get('entry_price'))) + (add_qty * current_price)) / total_qty
        state['weighted_avg_price'] = weighted_avg
        state['defense_stage'] = 1
        self._save_state()

        # Journal'a D1 tetiklenmesini kaydet
        defense_prices = self._defense_prices_for_entry(float(position.get('entry_price', 0) or 0))
        self.log_defense_activation(
            symbol=symbol,
            side=side,
            defense_level=1,
            defense_prices=defense_prices,
            weighted_avg=weighted_avg,
            position=position,
        )

        print(f"   🛡️  D1 gerçekleştirildi: yeni ağırlıklı ortalama {self._round_price(weighted_avg)}")
        try:
            from mina_motor_telegram import notify_d1
            entry = float(position.get('entry_price', 0) or 0)
            leverage = int(position.get('leverage', 4) or 4)
            if entry > 0:
                spot_chg = ((current_price - entry) / entry * 100) if side == 'LONG' else ((entry - current_price) / entry * 100)
                roe_pct = spot_chg * leverage
            else:
                roe_pct = 0.0
            notify_d1(
                symbol,
                side=side,
                leverage=leverage,
                roe_pct=roe_pct,
                margin_added=add_usdt,
                source="motor",
            )
        except Exception:
            pass
        return True

    def _execute_d2(self, position: Dict, current_price: float) -> bool:
        symbol = position.get('symbol')
        side = position.get('side')
        amount = float(position.get('amount', 0.0))
        state = self.position_states.get(symbol)

        if not state or amount <= 0:
            return False

        add_usdt = self.slot_size / 5
        add_qty = self._round_quantity(add_usdt / current_price, symbol)
        if add_qty <= 0:
            return False

        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        try:
            add_order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=add_qty,
                positionSide=side
            )
            if not self._verify_market_add(symbol, side, add_order):
                self._notify_defense_order_failure("D2 ekleme", symbol, side, "Market emri doğrulanamadı")
                return False
        except Exception as e:
            self._notify_defense_order_failure("D2 ekleme", symbol, side, str(e))
            return False

        total_qty = amount + add_qty
        weighted_avg = ((amount * float(position.get('entry_price'))) + (add_qty * current_price)) / total_qty
        state['weighted_avg_price'] = weighted_avg
        state['tp_disabled'] = True

        breakeven_price = self._round_price(weighted_avg * 1.0035, symbol)

        order = self._place_breakeven_escape_order(
            symbol, side, breakeven_price, total_qty, "D2"
        )
        if not order:
            return False

        try:
            state['d2_order_active'] = True
            state['d2_order_id'] = order.get('orderId')
            state['d2_order_type'] = order.get('_mina_order_type', ORDER_TYPE_TAKE_PROFIT_MARKET)
            state['defense_stage'] = 2
            state['d2_triggered_at'] = time.time()
            self._save_state()
            
            # Journal'a D2 tetiklenmesini kaydet
            defense_prices = self._defense_prices_for_entry(float(position.get('entry_price', 0) or 0))
            self.log_defense_activation(
                symbol=symbol,
                side=side,
                defense_level=2,
                defense_prices=defense_prices,
                weighted_avg=weighted_avg,
                position=position,
            )
            
            print(f"   🛡️  D2 yürütüldü: başa baş escape fiyatı {breakeven_price}")
            try:
                from mina_motor_telegram import notify_d2
                entry = float(position.get('entry_price', 0) or 0)
                leverage = int(position.get('leverage', 4) or 4)
                if entry > 0:
                    spot_chg = ((current_price - entry) / entry * 100) if side == 'LONG' else ((entry - current_price) / entry * 100)
                    roe_pct = spot_chg * leverage
                else:
                    roe_pct = 0.0
                notify_d2(
                    symbol,
                    side=side,
                    leverage=leverage,
                    roe_pct=roe_pct,
                    margin_added=add_usdt,
                    source="motor",
                )
            except Exception:
                pass
            return True
        except Exception as e:
            self._notify_defense_order_failure("D2", symbol, side, str(e))
            return False

    def _should_d2_time_stop(self, state: Dict) -> bool:
        """D2 tetiklendikten D2_TIME_STOP_H saat sonra TP/breakeven yoksa kapat."""
        ts = state.get('d2_triggered_at')
        if ts is None:
            return False
        try:
            elapsed = time.time() - float(ts)
        except (TypeError, ValueError):
            return False
        if elapsed < D2_TIME_STOP_H * 3600:
            return False
        if state.get('tp2_done'):
            return False
        if int(state.get('defense_stage', 0)) < 2 and not state.get('tp_disabled'):
            return False
        return True

    def execute_d2_time_stop(self, position: Dict, current_price: float) -> bool:
        """D2 zaman stopu — ortalama maliyet referanslı market tam kapama."""
        symbol = position.get('symbol')
        side = position.get('side')
        amount = float(position.get('amount', 0.0))
        state = self.position_states.get(symbol, {})

        if amount <= 0:
            return False

        self._cancel_d2_order(symbol, state)

        weighted_avg = float(state.get('weighted_avg_price') or position.get('entry_price', 0))
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        close_price = current_price
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            close_price = float(ticker['markPrice'])
        except Exception:
            pass

        try:
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=self._round_quantity(amount, symbol),
                positionSide=side,
            )
            pnl_usdt = (
                (close_price - weighted_avg) * amount
                if side == 'LONG'
                else (weighted_avg - close_price) * amount
            )
            pnl_percent = (pnl_usdt / (weighted_avg * amount)) * 100 if weighted_avg > 0 else 0
            roe_percent = (
                (pnl_usdt / state.get('initial_margin', 1)) * 100
                if state.get('initial_margin', 0) > 0
                else 0
            )
            self.log_position_close(
                symbol=symbol,
                side=side,
                close_price=close_price,
                qty=amount,
                close_reason='D2 Time Stop',
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_percent,
                roe_percent=roe_percent,
            )
            print(
                f"   ⏱️  D2 zaman stopu: {symbol} market kapama "
                f"avg={weighted_avg:.6f} mark={close_price:.6f}"
            )
            try:
                from mina_motor_telegram import notify_time_stop
                notify_time_stop(symbol, pnl_usdt)
            except Exception:
                pass
            self.reset_position_state(symbol)
            return True
        except Exception as e:
            print(f"   ❌ D2 zaman stopu hatası: {e}")
            return False

    def _execute_d3(self, position: Dict, current_price: float) -> bool:
        symbol = position.get('symbol')
        side = position.get('side')
        amount = float(position.get('amount', 0.0))
        state = self.position_states.get(symbol)

        if not state or amount <= 0:
            return False

        if side != 'LONG':
            print(f"   ⚠️  D3 yalnızca LONG için etkin: {symbol}")
            return False

        if not self._check_d3_sfp(symbol, side):
            print(f"   ⚠️  D3 SFP onayı yok: {symbol}")
            return False

        add_usdt = self.slot_size * 0.40
        add_qty = self._round_quantity(add_usdt / current_price, symbol)
        if add_qty <= 0:
            return False

        order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
        try:
            add_order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=add_qty,
                positionSide=side
            )
            if not self._verify_market_add(symbol, side, add_order):
                self._notify_defense_order_failure("D3 ekleme", symbol, side, "Market emri doğrulanamadı")
                return False
        except Exception as e:
            self._notify_defense_order_failure("D3 ekleme", symbol, side, str(e))
            return False

        total_qty = amount + add_qty
        weighted_avg = ((amount * float(position.get('entry_price'))) + (add_qty * current_price)) / total_qty
        state['weighted_avg_price'] = weighted_avg
        state['defense_stage'] = 3
        state['tp_disabled'] = False

        self._cancel_d2_order(symbol, state)

        breakeven_price = self._round_price(weighted_avg * 1.0035, symbol)
        order = self._place_breakeven_escape_order(
            symbol, side, breakeven_price, total_qty, "D3"
        )
        if not order:
            return False

        try:
            state['d3_order_id'] = order.get('orderId')
            state['d3_order_type'] = order.get('_mina_order_type', ORDER_TYPE_TAKE_PROFIT_MARKET)
            self._save_state()
            
            # Journal'a D3 tetiklenmesini kaydet
            defense_prices = self._defense_prices_for_entry(float(position.get('entry_price', 0) or 0))
            self.log_defense_activation(
                symbol=symbol,
                side=side,
                defense_level=3,
                defense_prices=defense_prices,
                weighted_avg=weighted_avg,
                position=position,
            )
            
            print(f"   🛡️  D3 tamamlandı: yeni TP kaçış emri {breakeven_price} fiyatına gönderildi")
            try:
                from mina_motor_telegram import notify_d3
                entry = float(position.get('entry_price', 0) or 0)
                leverage = int(position.get('leverage', 4) or 4)
                if entry > 0:
                    spot_chg = ((current_price - entry) / entry * 100) if side == 'LONG' else ((entry - current_price) / entry * 100)
                    roe_pct = spot_chg * leverage
                else:
                    roe_pct = 0.0
                notify_d3(
                    symbol,
                    side=side,
                    leverage=leverage,
                    roe_pct=roe_pct,
                    margin_added=add_usdt,
                    source="motor",
                )
            except Exception:
                pass
            return True
        except Exception as e:
            self._notify_defense_order_failure("D3", symbol, side, str(e))
            return False

    def execute_hard_stop(self, position: Dict) -> bool:
        symbol = position.get('symbol')
        amount = float(position.get('amount', 0.0))
        side = position.get('side')
        entry_price = position.get('entry_price')
        state = self.position_states.get(symbol, {})

        if amount <= 0:
            return False

        stop_price = self._round_price(entry_price * 0.75) if side == 'LONG' else self._round_price(entry_price / 0.75)
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        
        # Kapanış fiyatını oku (hard stop tetiklendiğinde yaklaşık fiyat)
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            close_price = float(ticker['markPrice'])
        except:
            close_price = stop_price  # Hard stop tetiklenme fiyatı
        
        already_past = (
            (side == 'LONG' and close_price <= stop_price)
            or (side == 'SHORT' and close_price >= stop_price)
        )

        try:
            if already_past:
                self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=self._round_quantity(amount, symbol),
                    positionSide=side
                )
                print(f"   🔥 HARD STOP tetiklendi (MARKET): {symbol} tam kapama mark={close_price}")
            else:
                self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_STOP_MARKET,
                    stopPrice=stop_price,
                    quantity=self._round_quantity(amount, symbol),
                    positionSide=side
                )
                print(f"   🔥 HARD STOP tetiklendi: {symbol} tam kapama stopPrice={stop_price}")

            pnl_usdt = (close_price - entry_price) * amount if side == 'LONG' else (entry_price - close_price) * amount
            pnl_percent = (pnl_usdt / (entry_price * amount)) * 100 if entry_price > 0 else 0
            roe_percent = (pnl_usdt / state.get('initial_margin', 1)) * 100 if state.get('initial_margin', 0) > 0 else 0

            self.log_position_close(
                symbol=symbol,
                side=side,
                close_price=close_price,
                qty=amount,
                close_reason='Hard Stop',
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_percent,
                roe_percent=roe_percent,
            )

            try:
                from mina_coin_lock import set_coin_cooldown, HARD_STOP_COOLDOWN_HOURS
                set_coin_cooldown(symbol, hours=HARD_STOP_COOLDOWN_HOURS, data_root=self.data_root)
                print(f"   ⏳ {symbol} hard stop cooldown {HARD_STOP_COOLDOWN_HOURS:.0f} saat")
            except Exception as e:
                print(f"   ⚠️  Cooldown yazılamadı: {e}")

            try:
                from mina_motor_telegram import notify_hard_stop
                notify_hard_stop(symbol, pnl_usdt)
            except Exception:
                pass

            self.reset_position_state(symbol)
            return True
        except Exception as e:
            print(f"   ❌ HARD STOP hatası: {e}")
            return False

    def _check_d3_sfp(self, symbol: str, side: str) -> bool:
        if side != 'LONG':
            return False

        try:
            klines_4h = self.client.futures_klines(symbol=symbol, interval='4h', limit=16)
            klines_5m = self.client.futures_klines(symbol=symbol, interval='5m', limit=6)
        except Exception as e:
            print(f"   ❌ D3 SFP klines okunamadi: {e}")
            return False

        if not klines_4h or not klines_5m:
            return False

        lows_4h = [float(k[3]) for k in klines_4h]
        opens_4h = [float(k[1]) for k in klines_4h]
        closes_4h = [float(k[4]) for k in klines_4h]
        support_low = min(lows_4h[-8:])
        support_high = support_low * 1.003

        last_4h = klines_4h[-1]
        last_4h_low = float(last_4h[3])
        last_4h_open = float(last_4h[1])
        last_4h_close = float(last_4h[4])

        if last_4h_low > support_low or last_4h_close <= support_low:
            return False

        if last_4h_close <= last_4h_open:
            return False

        last_5m = klines_5m[-1]
        last_5m_open = float(last_5m[1])
        last_5m_close = float(last_5m[4])

        if last_5m_close <= last_5m_open:
            return False

        if not (support_low <= last_5m_close <= support_high):
            return False

        print(f"   ✅ D3 SFP onayi: 4H destekte iğne + 5m bull bar kapatması bulundu")
        return True

    def _cancel_d2_order(self, symbol: str, state: Dict) -> None:
        d2_order_id = state.get('d2_order_id')
        if not d2_order_id:
            return

        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=d2_order_id)
            print(f"   🗑️  D2 kaçış emri iptal edildi: {d2_order_id}")
            state['d2_order_id'] = None
            state['d2_order_active'] = False
            self._save_state()
        except Exception as e:
            print(f"   ⚠️  D2 kaçış emri iptal edilemedi: {e}")

    # ---------------------------------------------------------------------
    # Execution helpers
    # ---------------------------------------------------------------------

    def execute_take_profit(self, position: Dict, level: int) -> bool:
        symbol = position.get('symbol')
        side = position.get('side')
        amount = float(position.get('amount', 0.0))
        state = self.position_states.get(symbol, {})

        if amount <= 0:
            return False

        if level == 1:
            close_qty = self._round_quantity(amount * 0.50, symbol)
            if close_qty <= 0:
                return False

            print(f"\n💰 TP1: {symbol} için %50 kısmi kapama")
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            # Kapanış fiyatını oku
            try:
                ticker = self.client.futures_mark_price(symbol=symbol)
                close_price = float(ticker['markPrice'])
            except:
                close_price = position.get('entry_price', 0)
            
            try:
                self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=close_qty,
                    positionSide=side
                )

                entry_price = state.get('weighted_avg_price', position.get('entry_price', 0))
                partial_pnl = (close_price - entry_price) * close_qty if side == 'LONG' else (entry_price - close_price) * close_qty
                partial_pct = (partial_pnl / (entry_price * close_qty)) * 100 if entry_price > 0 else 0
                partial_roe = (partial_pnl / state.get('initial_margin', 1)) * 100 if state.get('initial_margin', 0) > 0 else 0
            except Exception as e:
                print(f"   ❌ TP1 market kapama hatası: {e}")
                return False

            remaining_qty = self._round_quantity(amount - close_qty, symbol)
            if remaining_qty > 0:
                self.log_position_close(
                    symbol=symbol,
                    side=side,
                    close_price=close_price,
                    qty=close_qty,
                    close_reason='TP1 Partial',
                    pnl_usdt=partial_pnl,
                    pnl_percent=partial_pct,
                    roe_percent=partial_roe,
                    remaining_open_qty=remaining_qty,
                )
                stop_price = self._round_price(state.get('weighted_avg_price', position.get('entry_price')))
                try:
                    self.client.futures_create_order(
                        symbol=symbol,
                        side=order_side,
                        type=ORDER_TYPE_STOP_MARKET,
                        stopPrice=stop_price,
                        quantity=remaining_qty,
                        positionSide=side
                    )
                    print(f"   🛡️  Breakeven stop order kuruldu: {stop_price}")
                except Exception as e:
                    print(f"   ❌ Breakeven stop kurulamadı: {e}")

            state['tp1_done'] = True
            state['highest_price'] = position.get('entry_price')
            self._save_state()
            self._persist_tp_level(symbol, side, 1)
            try:
                from mina_motor_telegram import notify_tp1
                leverage = int(position.get('leverage', 4) or 4)
                notify_tp1(
                    symbol,
                    partial_pct,
                    partial_pnl,
                    side=side,
                    leverage=leverage,
                    entry_price=entry_price,
                    tp1_price=close_price,
                    source="motor",
                )
            except Exception:
                pass
            return True

        if level == 2:
            if state.get('tp_disabled'):
                print(f"   ⚠️  TP2 atlandı çünkü TP sistemi D2 ile donduruldu")
                return False

            is_ht = self._get_tp_type(position) == 'ht'
            close_qty = self._round_quantity(amount if is_ht else amount * 0.50, symbol)
            if close_qty <= 0:
                return False

            print(f"\n💰 TP2: {symbol} için kalan pozisyonun %50'si kapatılıyor")
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            # Kapanış fiyatını oku
            try:
                ticker = self.client.futures_mark_price(symbol=symbol)
                close_price = float(ticker['markPrice'])
            except:
                close_price = position.get('entry_price', 0)
            
            try:
                self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=close_qty,
                    positionSide=side
                )

                entry_price = state.get('weighted_avg_price', position.get('entry_price', 0))
                partial_pnl = (close_price - entry_price) * close_qty if side == 'LONG' else (entry_price - close_price) * close_qty
                partial_pct = (partial_pnl / (entry_price * close_qty)) * 100 if entry_price > 0 else 0
            except Exception as e:
                print(f"   ❌ TP2 market kapama hatası: {e}")
                return False

            remaining_qty = self._round_quantity(amount - close_qty, symbol)
            if remaining_qty > 0 and self.tp_rules[self._get_tp_type(position)]['trailing_callback_pct'] is not None:
                try:
                    self.client.futures_create_order(
                        symbol=symbol,
                        side=order_side,
                        type=ORDER_TYPE_TRAILING_STOP_MARKET,
                        quantity=remaining_qty,
                        positionSide=side,
                        callbackRate=self.tp_rules[self._get_tp_type(position)]['trailing_callback_pct']
                    )
                    print(f"   🏁 Trailing stop market emri gönderildi: callbackRate=%{self.tp_rules[self._get_tp_type(position)]['trailing_callback_pct']}")
                    state['trailing_order_active'] = True
                except Exception as e:
                    print(f"   ❌ Trailing stop emri gönderilemedi: {e}")

            state['tp2_done'] = True
            self._save_state()
            self._persist_tp_level(symbol, side, 2)
            peak = self._update_max_price(symbol, side, close_price)
            print(f"   📈 max_prices seed after TP2: {peak}")
            try:
                from mina_motor_telegram import notify_tp2
                leverage = int(position.get('leverage', 4) or 4)
                notify_tp2(
                    symbol,
                    partial_pct,
                    partial_pnl,
                    side=side,
                    leverage=leverage,
                    entry_price=entry_price,
                    tp2_price=close_price,
                    source="motor",
                )
            except Exception:
                pass
            return True

        return False

    def execute_trailing_stop(self, position: Dict) -> bool:
        symbol = position.get('symbol')
        amount = float(position.get('amount', 0.0))
        side = position.get('side')
        state = self.position_states.get(symbol, {})

        if amount <= 0:
            return False

        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        
        # Kapanış fiyatını oku
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            close_price = float(ticker['markPrice'])
        except:
            close_price = position.get('entry_price', 0)
        
        try:
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=self._round_quantity(amount, symbol),
                positionSide=side
            )
            
            # Journal'a Trailing kapanışını kaydet
            entry_price = state.get('weighted_avg_price', position.get('entry_price', 0))
            pnl_usdt = (close_price - entry_price) * amount if side == 'LONG' else (entry_price - close_price) * amount
            pnl_percent = (pnl_usdt / (entry_price * amount)) * 100 if entry_price > 0 else 0
            roe_percent = (pnl_usdt / state.get('initial_margin', 1)) * 100 if state.get('initial_margin', 0) > 0 else 0
            
            self.log_position_close(
                symbol=symbol,
                side=side,
                close_price=close_price,
                qty=amount,
                close_reason='Trailing',
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_percent,
                roe_percent=roe_percent,
            )

            try:
                from mina_motor_telegram import notify_trailing_closed
                leverage = int(position.get('leverage', 4) or 4)
                notify_trailing_closed(
                    symbol,
                    pnl_usdt,
                    side=side,
                    leverage=leverage,
                    peak_price=state.get('highest_price'),
                    exit_price=close_price,
                    pnl_pct=pnl_percent,
                    source="motor",
                )
            except Exception:
                pass
            
            self.reset_position_state(symbol)
            return True
        except Exception as e:
            print(f"   ❌ Trailing stop kapatma hatası: {e}")
            return False

    def execute_manual_close(
        self, position: Dict, current_price: float, close_reason: str,
    ) -> bool:
        """Manuel stop/TP — tam MARKET kapama."""
        symbol = position.get('symbol')
        amount = float(position.get('amount', 0.0))
        side = position.get('side')
        state = self.position_states.get(symbol, {})
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY

        if amount <= 0:
            return False

        close_price = current_price
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            close_price = float(ticker['markPrice'])
        except Exception:
            pass

        order = self._futures_create_order(
            label=close_reason,
            symbol=symbol,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=self._round_quantity(amount, symbol),
            positionSide=side,
        )
        if not order:
            return False

        entry_price = state.get('weighted_avg_price', position.get('entry_price', 0))
        pnl_usdt = (
            (close_price - entry_price) * amount
            if side == 'LONG'
            else (entry_price - close_price) * amount
        )
        pnl_percent = (pnl_usdt / (entry_price * amount)) * 100 if entry_price > 0 else 0
        roe_percent = (
            (pnl_usdt / state.get('initial_margin', 1)) * 100
            if state.get('initial_margin', 0) > 0
            else 0
        )

        self.log_position_close(
            symbol=symbol,
            side=side,
            close_price=close_price,
            qty=amount,
            close_reason=close_reason,
            pnl_usdt=pnl_usdt,
            pnl_percent=pnl_percent,
            roe_percent=roe_percent,
        )
        try:
            from mina_motor_telegram import notify_manual_stop, notify_manual_tp
            if close_reason == "Manuel Stop":
                notify_manual_stop(symbol)
            elif close_reason == "Manuel TP":
                notify_manual_tp(symbol)
        except Exception:
            pass
        self.reset_position_state(symbol)
        print(f"   ✅ {close_reason}: {symbol} {side} @ {close_price}")
        return True

    def execute_stop_loss(self, position: Dict) -> bool:
        symbol = position.get('symbol')
        amount = float(position.get('amount', 0.0))
        side = position.get('side')
        state = self.position_states.get(symbol, {})
        order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY

        if amount <= 0:
            return False

        # Kapanış fiyatını oku
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            close_price = float(ticker['markPrice'])
        except:
            close_price = position.get('entry_price', 0)
        
        try:
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=self._round_quantity(amount, symbol),
                positionSide=side
            )
            
            # Journal'a Stop Loss kapanışını kaydet
            entry_price = state.get('weighted_avg_price', position.get('entry_price', 0))
            pnl_usdt = (close_price - entry_price) * amount if side == 'LONG' else (entry_price - close_price) * amount
            pnl_percent = (pnl_usdt / (entry_price * amount)) * 100 if entry_price > 0 else 0
            roe_percent = (pnl_usdt / state.get('initial_margin', 1)) * 100 if state.get('initial_margin', 0) > 0 else 0
            
            self.log_position_close(
                symbol=symbol,
                side=side,
                close_price=close_price,
                qty=amount,
                close_reason='Stop Loss',
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_percent,
                roe_percent=roe_percent,
            )

            try:
                from mina_motor_telegram import notify_stop_loss
                notify_stop_loss(symbol, pnl_usdt)
            except Exception:
                pass

            self.reset_position_state(symbol)
            return True
        except Exception as e:
            print(f"   ❌ Stop loss kapatma hatası: {e}")
            return False

    def _get_effective_entry_price(self, position: Dict) -> float:
        symbol = position.get('symbol')
        state = self.position_states.get(symbol, {})
        return state.get('weighted_avg_price', position.get('entry_price'))

    def _ensure_lot_step_cache(self) -> None:
        if self._exchange_info_loaded:
            return
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                sym = s['symbol']
                step = 0.001
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step = float(f['stepSize'])
                        break
                self._lot_step_cache[sym] = step
            self._exchange_info_loaded = True
        except Exception:
            self._lot_step_cache.setdefault('', 0.001)

    def _get_lot_step_size(self, symbol: str) -> float:
        self._ensure_lot_step_cache()
        return self._lot_step_cache.get(symbol, 0.001)

    def _round_quantity(self, quantity: float, symbol: str) -> float:
        if quantity <= 0:
            return 0.0
        step = self._get_lot_step_size(symbol)
        if step <= 0:
            return round(quantity, 8)
        q = Decimal(str(quantity))
        s = Decimal(str(step))
        rounded = (q / s).to_integral_value(rounding=ROUND_DOWN) * s
        return float(rounded)

    def _round_price(self, price: float, symbol: Optional[str] = None) -> float:
        price = max(float(price), 0.0)
        if symbol:
            try:
                from mina_exchange_info import symbol_filters
                tick = float(symbol_filters(self.client, symbol).get("tickSize") or 0.01)
                if tick > 0:
                    p = Decimal(str(price))
                    t = Decimal(str(tick))
                    return float((p / t).to_integral_value(rounding=ROUND_DOWN) * t)
            except Exception:
                pass
        if price < 1:
            return round(price, 6)
        return round(price, 2)

    def _get_tp_type(self, position: Dict) -> str:
        leverage = position.get('leverage')
        rules = self._rules_for_leverage(int(leverage or 0))
        return rules.get('tp_type') or self.leverage_rules.get(leverage, {}).get('tp_type', 'standard')

    def _is_tp_hit(self, current_price: float, target_price: float, side: str) -> bool:
        if side == 'LONG':
            return current_price >= target_price
        return current_price <= target_price

    # ─────────────────────────────────────────────────────────────
    # GLOBAL SLOT KAPISI KİLİDİ & ACİL TASFIYE SİSTEMİ
    # ─────────────────────────────────────────────────────────────

    def validate_slot_limit(self) -> Dict:
        """
        Global slot kapısı kontrolü.
        
        Eğer Binance'ten okunan açık pozisyon sayısı 10'u aşarsa:
        1. Kritis alarm logla
        2. Fazlasını anında MARKET emri ile kapat
        3. Kasa güvenliğini sağla
        
        Returns: {
            'status': 'OK' | 'OVERFLOW',
            'open_count': int,
            'max_slots': int,
            'overflow_count': int,
            'closed': [{'symbol': 'BTCUSDT', 'side': 'LONG', 'qty': 0.001}],
            'errors': [error_msg]
        }
        """
        max_slots = 10
        
        try:
            # ── Açık pozisyon sayısını taze oku ─────────────────────────
            positions = self.client.futures_position_information()
            open_positions = [
                p for p in positions 
                if float(p['positionAmt']) != 0
            ]
            open_count = len(open_positions)
            
            result = {
                'status': 'OK',
                'open_count': open_count,
                'max_slots': max_slots,
                'overflow_count': 0,
                'closed': [],
                'errors': []
            }
            
            # ── Kapasite kontrolü ─────────────────────────────────────
            if open_count > max_slots:
                overflow = open_count - max_slots
                result['status'] = 'OVERFLOW'
                result['overflow_count'] = overflow
                
                # KRİTİK ALARM
                print(f"\n{'='*70}")
                print(f"⛔ KRİTİK SLOT LİMİTİ AŞILDI!")
                print(f"{'='*70}")
                print(f"📊 Açık pozisyon: {open_count} / {max_slots}")
                print(f"🚨 Kapasite aşımı: +{overflow}")
                print(f"⏰ Acil Tasfiye BAŞLATILIYOR...")
                print(f"{'='*70}\n")
                
                # ── Tasfiye işlemini başlat ──────────────────────────────
                closed = self._emergency_close_overflow_positions(
                    open_positions, max_slots
                )
                result['closed'] = closed
                
            return result
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'open_count': 0,
                'max_slots': max_slots,
                'overflow_count': 0,
                'closed': [],
                'errors': [str(e)]
            }

    def _emergency_close_overflow_positions(self, open_positions: list, max_slots: int) -> list:
        """
        Kapasite aşan pozisyonları acil tasfiye et.
        
        Binance'ten okunan sıradaki ilk (10 + k) pozisyonlardan,
        10. pozisyondan sonrakileri MARKET emri ile kapat.
        
        Args:
            open_positions: Binance'ten gelen açık pozisyon listesi
            max_slots: Maksimum slot sayısı (10)
        
        Returns:
            Kapatılan pozisyonların listesi
        """
        closed = []
        
        # 10. pozisyondan sonrakileri kapat
        overflow_positions = open_positions[max_slots:]
        
        for i, pos_info in enumerate(overflow_positions, 1):
            symbol = pos_info['symbol']
            amount = abs(float(pos_info['positionAmt']))
            side = 'LONG' if float(pos_info['positionAmt']) > 0 else 'SHORT'
            entry_price = float(pos_info['entryPrice'])
            mark_price = float(pos_info['markPrice'])
            
            if amount <= 0:
                continue
            
            # ROE hesapla (bilgi amaçlı)
            if side == 'LONG':
                pnl_pct = ((mark_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - mark_price) / entry_price) * 100
            
            pnl_usdt = float(pos_info.get('unRealizedProfit', 0))
            
            print(f"   🗑️  Tasfiye #{i}: {symbol} {side}")
            print(f"       💰 Giriş: ${entry_price:.4f} | Şuan: ${mark_price:.4f}")
            print(f"       📊 PnL: {pnl_pct:+.2f}% (${pnl_usdt:+.2f})")
            print(f"       ⚡ Miktar: {amount}")
            
            qty_to_close = self._round_quantity(amount, symbol)
            
            if qty_to_close <= 0:
                print(f"       ⚠️  Kapatılacak miktar 0 — atlanıyor\n")
                continue
            
            order_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
            
            try:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type=ORDER_TYPE_MARKET,
                    quantity=qty_to_close,
                    positionSide=side
                )
                
                # Journal'a acil tasfiyeyi kaydet
                roe_percent = (pnl_usdt / (entry_price * qty_to_close / 10)) * 100  # Yaklaşık ROE
                
                self.log_position_close(
                    symbol=symbol,
                    side=side,
                    close_price=mark_price,
                    qty=qty_to_close,
                    close_reason='Acil Tasfiye',
                    pnl_usdt=pnl_usdt,
                    pnl_percent=pnl_pct,
                    roe_percent=roe_percent,
                )
                
                print(f"       ✅ KAPATILDI! Order ID: {order.get('orderId')}")
                print(f"       💾 Kasa güvenliğe alındı.\n")
                
                closed.append({
                    'symbol': symbol,
                    'side': side,
                    'qty': qty_to_close,
                    'entry_price': entry_price,
                    'close_price': mark_price,
                    'pnl_usdt': pnl_usdt,
                    'pnl_pct': pnl_pct,
                    'order_id': order.get('orderId')
                })
                
                # State'ten sil
                self.reset_position_state(symbol)
                
            except Exception as e:
                error_msg = str(e)
                print(f"       ❌ HATA: {error_msg}\n")
        
        return closed

    def _get_symbol_precision(self, symbol: str) -> int:
        """Sembol için step size ondalık basamak sayısı (cache'li)."""
        step = self._get_lot_step_size(symbol)
        if step >= 1:
            return 0
        step_str = f"{step:.12f}".rstrip('0')
        if '.' not in step_str:
            return 0
        return len(step_str.split('.')[1])

    # ─────────────────────────────────────────────────────────────
    # JOURNAL LOGGING — DERR İntegrasyonu
    # ─────────────────────────────────────────────────────────────

    def _trade_id_for(self, symbol: str, side: str) -> Optional[int]:
        """pos_key ile trade_id; eski symbol-only kayıtlar + journal fallback."""
        key = self._pos_key(symbol, side)
        if key in self.trade_ids:
            return self.trade_ids[key]
        if symbol in self.trade_ids:
            return self.trade_ids[symbol]
        row = self._open_trade_from_journal(symbol, side)
        if row and row.get('id') is not None:
            tid = int(row['id'])
            self.trade_ids[key] = tid
            return tid
        return None

    def _ensure_trade_id(self, symbol: str, side: str, position: Dict) -> Optional[int]:
        """Journal'da açık trade yoksa yetim pozisyon kaydı oluştur."""
        tid = self._trade_id_for(symbol, side)
        if tid is not None or not self.journal:
            return tid

        from mina_signal_source import detect_orphan_signal_source, record_position_source

        orphan_src = detect_orphan_signal_source(symbol, side)
        record_position_source(symbol, side, orphan_src)
        leverage = int(position.get('leverage', 4) or 4)
        entry = float(position.get('entry_price', 0) or 0)
        qty = float(position.get('amount', 0) or 0)
        margin = float(position.get('isolated_margin') or 0)
        if margin <= 0 and entry > 0 and qty > 0:
            margin = round((entry * qty) / max(leverage, 1), 4)

        tid = self.journal.log_trade_open(
            symbol=symbol,
            side=side,
            leverage=leverage,
            entry_price=entry,
            qty=qty,
            initial_margin=margin,
            signal_source=orphan_src,
        )
        if tid > 0:
            self.trade_ids[self._pos_key(symbol, side)] = tid
            print(f"📔 [Journal] Yetim pozisyon kaydı: {symbol} {side} id={tid}")
            return tid
        return None

    def _defense_prices_for_entry(self, entry_price: float) -> Dict[str, float]:
        return {
            'D1': entry_price * 0.95,
            'D2': entry_price * 0.88,
            'D3': entry_price * 0.75,
        }

    def _backfill_journal_defense_if_needed(
        self,
        symbol: str,
        side: str,
        position: Dict,
        target_level: int,
    ) -> None:
        if target_level <= 0:
            return
        if self._defense_level_from_journal(symbol, side) >= target_level:
            return
        state = self.position_states.get(symbol, {})
        entry = self._get_initial_entry(
            symbol, side, float(position.get('entry_price', 0) or 0)
        )
        weighted_avg = float(
            state.get('weighted_avg_price') or position.get('entry_price', 0) or entry
        )
        self.log_defense_activation(
            symbol=symbol,
            side=side,
            defense_level=target_level,
            defense_prices=self._defense_prices_for_entry(entry),
            weighted_avg=weighted_avg,
            position=position,
        )

    def log_position_open(
        self,
        symbol: str,
        side: str,
        leverage: int,
        entry_price: float,
        qty: float,
        initial_margin: float,
        signal_source: Optional[str] = None,
        send_telegram: bool = True,
    ) -> None:
        """Pozisyon açıldığında journal'a kaydet + kaynak logu."""
        from mina_signal_source import (
            format_open_log,
            normalize_source_code,
            record_position_source,
        )

        src = normalize_source_code(signal_source)
        msg = format_open_log(src, symbol, side)
        print(msg)

        try:
            import logging
            logging.getLogger("MİNA_v2").info(msg)
        except Exception:
            pass

        record_position_source(symbol, side, src)

        if send_telegram:
            try:
                from mina_motor_telegram import notify_position_open
                notify_position_open(symbol, side, leverage, entry_price, initial_margin, src)
            except Exception:
                pass

        if not self.journal:
            return

        try:
            trade_id = self.journal.log_trade_open(
                symbol=symbol,
                side=side,
                leverage=leverage,
                entry_price=entry_price,
                qty=qty,
                initial_margin=initial_margin,
                signal_source=src,
            )
            if trade_id > 0:
                self.trade_ids[self._pos_key(symbol, side)] = trade_id
                self._save_state()
                try:
                    from mina_copy_trading import get_copy_engine
                    eng = get_copy_engine()
                    if eng:
                        eng.on_master_open(
                            symbol=symbol,
                            side=side,
                            leverage=leverage,
                            entry_price=entry_price,
                            qty=qty,
                            initial_margin=initial_margin,
                            master_trade_id=trade_id,
                        )
                except Exception as copy_err:
                    print(f"⚠️  Copy trade open: {copy_err}")
        except Exception as e:
            print(f"❌ Journal log_position_open hatası: {e}")

    def log_defense_activation(self, symbol: str, side: str, defense_level: int,
                              defense_prices: Dict, weighted_avg: float,
                              position: Optional[Dict] = None) -> None:
        """Savunma tetiklendiğinde journal'a kaydet."""
        trade_id = self._trade_id_for(symbol, side)
        if trade_id is None and position is not None:
            trade_id = self._ensure_trade_id(symbol, side, position)
        if not self.journal or trade_id is None:
            print(
                f"⚠️  Journal defense yazılamadı (trade_id yok): "
                f"{symbol} {side} D{defense_level}"
            )
            return

        try:
            self.journal.log_defense_triggered(
                trade_id=trade_id,
                defense_level=defense_level,
                defense_prices=defense_prices,
                weighted_avg=weighted_avg,
            )
        except Exception as e:
            print(f"❌ Journal log_defense_activation hatası: {e}")

    def _cancel_merter_dca_limits(self, symbol: str) -> int:
        """Motor kapanışında kalan Merter DCA limit emirlerini iptal et."""
        cancelled = 0
        try:
            for o in self.client.futures_get_open_orders(symbol=symbol):
                if o.get("type") != "LIMIT":
                    continue
                side = str(o.get("side", "")).upper()
                if side != "BUY":
                    continue
                self.client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
                cancelled += 1
                print(f"   🚫 DCA limit iptal: {symbol} orderId={o['orderId']} price={o.get('price')}")
        except Exception as e:
            print(f"   ⚠️  DCA limit iptal hatası {symbol}: {e}")
        return cancelled

    def log_position_close(
        self,
        symbol: str,
        side: str,
        close_price: float,
        qty: float,
        close_reason: str,
        pnl_usdt: float,
        pnl_percent: float,
        roe_percent: float,
        remaining_open_qty: float | None = None,
    ) -> None:
        """Tam kapanış veya kısmi TP sonrası DERR güncelle."""
        trade_id = self._trade_id_for(symbol, side)
        if not self.journal or trade_id is None:
            print(f"⚠️  Journal close atlandı (trade_id yok): {symbol} {side}")
            return

        if remaining_open_qty is not None and remaining_open_qty > 0:
            state = self.position_states.get(symbol, {})
            old_margin = float(state.get("initial_margin") or 0)
            old_qty = float(qty) + float(remaining_open_qty)
            ratio = float(remaining_open_qty) / old_qty if old_qty > 0 else 1.0
            new_margin = old_margin * ratio if old_margin > 0 else old_margin
            try:
                self.journal.reconcile_open_qty(trade_id, remaining_open_qty, new_margin)
                state["initial_margin"] = new_margin
                self._save_state()
                print(
                    f"📔 [Journal] Kısmi kapanış ({close_reason}): {symbol} "
                    f"kalan qty={remaining_open_qty}"
                )
                try:
                    from mina_copy_trading import get_copy_engine
                    eng = get_copy_engine()
                    if eng:
                        close_ratio = float(qty) / old_qty if old_qty > 0 else 0.5
                        eng.on_master_partial_close(
                            symbol=symbol,
                            side=side,
                            close_price=close_price,
                            close_ratio=close_ratio,
                            close_reason=close_reason,
                        )
                except Exception as copy_err:
                    print(f"⚠️  Copy trade partial: {copy_err}")
            except Exception as e:
                print(f"❌ Journal kısmi qty güncelleme hatası: {e}")
            return

        self._cancel_merter_dca_limits(symbol)
        try:
            self.journal.log_trade_close(
                trade_id=trade_id,
                close_price=close_price,
                qty=qty,
                close_reason=close_reason,
                pnl_usdt=pnl_usdt,
                pnl_percent=pnl_percent,
                roe_percent=roe_percent,
            )
            key = self._pos_key(symbol, side)
            self.trade_ids.pop(key, None)
            self.trade_ids.pop(symbol, None)
            self._save_state()

            try:
                from mina_signal_source import clear_position_source
                clear_position_source(symbol, side)
            except Exception:
                pass

            try:
                from mina_copy_trading import get_copy_engine
                eng = get_copy_engine()
                if eng:
                    eng.on_master_close(
                        symbol=symbol,
                        side=side,
                        close_price=close_price,
                        close_reason=close_reason,
                        pnl_usdt=pnl_usdt,
                    )
            except Exception as copy_err:
                print(f"⚠️  Copy trade close: {copy_err}")

            try:
                from signal_bot.signal_slot_bridge import try_fill_freed_slot
                try_fill_freed_slot(self)
            except Exception as bridge_err:
                print(f"⚠️  Slot bridge hatası: {bridge_err}")
        except Exception as e:
            print(f"❌ Journal log_position_close hatası: {e}")


if __name__ == '__main__':
    print('MinaPositionManager yükleme testi')
