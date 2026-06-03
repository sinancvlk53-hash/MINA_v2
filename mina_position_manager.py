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
            }
        }

        self.defense_rules = {
            1: {'trigger_multiplier': 0.95, 'slot_ratio': 0.20},
            2: {'trigger_multiplier': 0.88, 'slot_ratio': 0.20},
            3: {'trigger_multiplier': 0.75, 'slot_ratio': 0.40},
        }

        self.state_file = os.path.join(self.data_root, 'mina_position_state.json')
        self._load_state()
        self._load_trade_ids_from_journal()

    # ---------------------------------------------------------------------
    # Binance ↔ disk senkronizasyonu
    # ---------------------------------------------------------------------

    @staticmethod
    def _pos_key(symbol: str, side: str) -> str:
        return mt.pos_key(symbol, side)

    def _get_initial_entry(self, symbol: str, side: str, fallback: float) -> float:
        prices = mt.load_json(mt.INITIAL_PRICE_FILE)
        return float(prices.get(self._pos_key(symbol, side), fallback))

    def sync_reality_from_binance(self, verbose: bool = True) -> Dict[str, Any]:
        """Açık pozisyonları Binance'ten okuyup tracking JSON + DERR ile hizalar."""
        from position_manager import PositionManager  # noqa: circular at module level

        pm = PositionManager(self.client)
        positions = pm.get_all_positions()
        report: Dict[str, Any] = {
            'open_count': len(positions),
            'synced_keys': [],
            'defense_reset': [],
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
            initial_prices[key] = entry
            initial_margins[key] = round(margin, 4) if margin > 0 else round((entry * pos['amount']) / max(leverage, 1), 4)
            defense_levels[key] = 0
            tp_levels[key] = 0
            max_prices[key] = mark

            report['synced_keys'].append({
                'key': key,
                'old_initial_entry': old_entry,
                'new_initial_entry': entry,
                'mark': mark,
                'd1_long': round(entry * 0.95, 8) if side == 'LONG' else round(entry / 0.95, 8),
                'd2_long': round(entry * 0.88, 8) if side == 'LONG' else round(entry / 1.12, 8),
            })
            report['defense_reset'].append(key)
            report['max_prices_seeded'].append({key: mark})

            self.init_position_state(symbol, entry)
            state = self.position_states.get(symbol, {})
            state['defense_stage'] = 0
            state['tp1_done'] = False
            state['tp2_done'] = False
            state['highest_price'] = mark
            state['weighted_avg_price'] = entry
            self._save_state()

            if self.journal:
                cursor = self.journal.conn.cursor()
                cursor.execute(
                    "SELECT id FROM trades WHERE symbol=? AND side=? AND status='open' ORDER BY id DESC LIMIT 1",
                    (symbol, side),
                )
                row = cursor.fetchone()
                if row:
                    self.trade_ids[key] = int(row['id'])
                else:
                    tid = self.journal.log_trade_open(
                        symbol=symbol,
                        side=side,
                        leverage=leverage,
                        entry_price=entry,
                        qty=float(pos['amount']),
                        initial_margin=initial_margins[key],
                    )
                    if tid > 0:
                        self.trade_ids[key] = tid
                        report['journal_opened'].append({'key': key, 'trade_id': tid})

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
                    close_reason='Reconciliation (Binance kapalı)',
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
                    'reason': 'Reconciliation (Binance kapalı)',
                    'close_price': close_price,
                    'pnl_usdt': round(pnl_usdt, 4),
                })
        except Exception as e:
            print(f"❌ Journal reconcile hatası: {e}")

        if closed_report:
            self._save_state()
        return closed_report

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
        data[self._pos_key(symbol, side)] = level
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

    def init_position_state(self, symbol: str, entry_price: float) -> None:
        """Yeni pozisyon için başlangıç state'i oluşturur."""
        self.position_states[symbol] = {
            'entry_price': entry_price,
            'tp1_done': False,
            'tp2_done': False,
            'highest_price': entry_price,
            'defense_stage': 0,
            'd2_order_active': False,
            'd2_order_id': None,
            'd3_order_id': None,
            'tp_disabled': False,
            'weighted_avg_price': entry_price,
        }
        self._save_state()

    def reset_position_state(self, symbol: str) -> None:
        if symbol in self.position_states:
            del self.position_states[symbol]
            self._save_state()

    # ---------------------------------------------------------------------
    # Public decision API
    # ---------------------------------------------------------------------

    def evaluate_position(self, position: Dict, current_price: float) -> Dict:
        """Pozisyona göre bir aksiyon döndürür."""
        leverage = position.get('leverage')
        symbol = position.get('symbol')
        side = position.get('side')
        entry_price = position.get('entry_price')

        rules = self.leverage_rules.get(leverage)
        if rules is None:
            return {'action': 'hold', 'reason': f'Bilinmeyen kaldıraç: {leverage}x'}

        state = self.position_states.get(symbol)
        if state is None:
            self.init_position_state(symbol, entry_price)
            state = self.position_states[symbol]

        if rules['has_defense']:
            defense_level = self.check_spot_defense_trigger(position, current_price)
            if defense_level > 0:
                return {
                    'action': 'defense',
                    'defense_level': defense_level,
                    'reason': f'D{defense_level} spot fiyat tetiklendi'
                }

        if rules['stop_loss_pct'] is not None:
            stop_price = self.calculate_stop_loss_price(entry_price, leverage, side)
            if self._is_stop_loss_hit(current_price, stop_price, side):
                return {
                    'action': 'stop_loss',
                    'reason': f'Stop-loss fiyatı aşıldı ({stop_price})'
                }

        tp_type = rules['tp_type']
        tp_rules = self.tp_rules[tp_type]

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
        if action_type == 'stop_loss':
            return self.execute_stop_loss(position)
        if action_type == 'take_profit':
            return self.execute_take_profit(position, action['level'])
        if action_type == 'trailing_stop':
            return self.execute_trailing_stop(position)

        return False

    # ---------------------------------------------------------------------
    # TP / trailing helpers
    # ---------------------------------------------------------------------

    def calculate_tp_price(self, entry_price: float, level: int, tp_type: str) -> float:
        key = 'tp1_multiplier' if level == 1 else 'tp2_multiplier'
        return entry_price * self.tp_rules[tp_type][key]

    def check_take_profit(self, position: Dict, current_price: float, tp_rules: Dict) -> Optional[Dict]:
        symbol = position.get('symbol')
        side = position.get('side')
        state = self.position_states.get(symbol, {})

        if state.get('tp_disabled'):
            return None

        effective_entry = self._get_effective_entry_price(position)

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
        rules = self.leverage_rules.get(leverage, {})
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
        file_defense = mt.load_json(mt.DEFENSE_FILE).get(self._pos_key(symbol, side), 0)
        current_stage = max(int(state.get('defense_stage', 0)), int(file_defense))

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

        state['defense_stage'] = defense_level
        self._save_state()
        self._persist_defense_level(symbol, side, defense_level)

        if defense_level == 1:
            return self._execute_d1(position, current_price)
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
        defense_prices = {
            'D1': position.get('entry_price', 0) * 0.95,
            'D2': position.get('entry_price', 0) * 0.88,
            'D3': position.get('entry_price', 0) * 0.75
        }
        self.log_defense_activation(
            symbol=symbol,
            side=side,
            defense_level=1,
            defense_prices=defense_prices,
            weighted_avg=weighted_avg,
        )

        print(f"   🛡️  D1 gerçekleştirildi: yeni ağırlıklı ortalama {self._round_price(weighted_avg)}")
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
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=add_qty,
                positionSide=side
            )
        except Exception as e:
            print(f"   ❌ D2 ekleme hatası: {e}")
            return False

        total_qty = amount + add_qty
        weighted_avg = ((amount * float(position.get('entry_price'))) + (add_qty * current_price)) / total_qty
        state['weighted_avg_price'] = weighted_avg
        state['tp_disabled'] = True

        breakeven_price = self._round_price(weighted_avg * 1.0035)
        escape_side = SIDE_SELL if side == 'LONG' else SIDE_BUY

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=escape_side,
                type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=breakeven_price,
                quantity=self._round_quantity(total_qty, symbol),
                positionSide=side
            )
            state['d2_order_active'] = True
            state['d2_order_id'] = order.get('orderId')
            state['defense_stage'] = 2
            self._save_state()
            
            # Journal'a D2 tetiklenmesini kaydet
            defense_prices = {
                'D1': position.get('entry_price', 0) * 0.95,
                'D2': position.get('entry_price', 0) * 0.88,
                'D3': position.get('entry_price', 0) * 0.75
            }
            self.log_defense_activation(
                symbol=symbol,
                side=side,
                defense_level=2,
                defense_prices=defense_prices,
                weighted_avg=weighted_avg,
            )
            
            print(f"   🛡️  D2 yürütüldü: başa baş escape fiyatı {breakeven_price}")
            return True
        except Exception as e:
            print(f"   ❌ D2 kaçış emri hatası: {e}")
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
            self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=add_qty,
                positionSide=side
            )
        except Exception as e:
            print(f"   ❌ D3 ekleme hatası: {e}")
            return False

        total_qty = amount + add_qty
        weighted_avg = ((amount * float(position.get('entry_price'))) + (add_qty * current_price)) / total_qty
        state['weighted_avg_price'] = weighted_avg
        state['defense_stage'] = 3
        state['tp_disabled'] = False

        self._cancel_d2_order(symbol, state)

        breakeven_price = self._round_price(weighted_avg * 1.0035)
        escape_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=escape_side,
                type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=breakeven_price,
                quantity=self._round_quantity(total_qty, symbol),
                positionSide=side
            )
            state['d3_order_id'] = order.get('orderId')
            self._save_state()
            
            # Journal'a D3 tetiklenmesini kaydet
            defense_prices = {
                'D1': position.get('entry_price', 0) * 0.95,
                'D2': position.get('entry_price', 0) * 0.88,
                'D3': position.get('entry_price', 0) * 0.75
            }
            self.log_defense_activation(
                symbol=symbol,
                side=side,
                defense_level=3,
                defense_prices=defense_prices,
                weighted_avg=weighted_avg,
            )
            
            print(f"   🛡️  D3 tamamlandı: yeni TP kaçış emri {breakeven_price} fiyatına gönderildi")
            return True
        except Exception as e:
            print(f"   ❌ D3 kaçış emri hatası: {e}")
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
                
                # TP1 kısmi kapama — journal tam kapanış trailing/stop'ta yazılır
            except Exception as e:
                print(f"   ❌ TP1 market kapama hatası: {e}")
                return False

            remaining_qty = self._round_quantity(amount - close_qty, symbol)
            if remaining_qty > 0:
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
            return True

        if level == 2:
            if state.get('tp_disabled'):
                print(f"   ⚠️  TP2 atlandı çünkü TP sistemi D2 ile donduruldu")
                return False

            close_qty = self._round_quantity(amount * 0.50, symbol)
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
                
                # TP2 kısmi kapama — journal tam kapanış trailing/stop'ta yazılır
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
            
            self.reset_position_state(symbol)
            return True
        except Exception as e:
            print(f"   ❌ Trailing stop kapatma hatası: {e}")
            return False

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

    def _round_price(self, price: float) -> float:
        return round(max(price, 0.0), 2)

    def _get_tp_type(self, position: Dict) -> str:
        leverage = position.get('leverage')
        return self.leverage_rules.get(leverage, {}).get('tp_type', 'standard')

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
        """pos_key ile trade_id; eski symbol-only kayıtlar için geriye dönük uyum."""
        key = self._pos_key(symbol, side)
        if key in self.trade_ids:
            return self.trade_ids[key]
        if symbol in self.trade_ids:
            return self.trade_ids[symbol]
        return None

    def log_position_open(self, symbol: str, side: str, leverage: int,
                         entry_price: float, qty: float, initial_margin: float) -> None:
        """Pozisyon açıldığında journal'a kaydet."""
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
            )
            if trade_id > 0:
                self.trade_ids[self._pos_key(symbol, side)] = trade_id
                self._save_state()
        except Exception as e:
            print(f"❌ Journal log_position_open hatası: {e}")

    def log_defense_activation(self, symbol: str, side: str, defense_level: int,
                              defense_prices: Dict, weighted_avg: float) -> None:
        """Savunma tetiklendiğinde journal'a kaydet."""
        trade_id = self._trade_id_for(symbol, side)
        if not self.journal or trade_id is None:
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
    ) -> None:
        """Pozisyon tamamen kapandığında journal.log_trade_close çağırır."""
        trade_id = self._trade_id_for(symbol, side)
        if not self.journal or trade_id is None:
            print(f"⚠️  Journal close atlandı (trade_id yok): {symbol} {side}")
            return

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
                from signal_bot.signal_slot_bridge import try_fill_freed_slot
                try_fill_freed_slot(self)
            except Exception as bridge_err:
                print(f"⚠️  Slot bridge hatası: {bridge_err}")
        except Exception as e:
            print(f"❌ Journal log_position_close hatası: {e}")


if __name__ == '__main__':
    print('MinaPositionManager yükleme testi')
