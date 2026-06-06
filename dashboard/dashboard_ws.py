#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MINA v2 — Dashboard WebSocket Server  port 8765
Binance pozisyon sayısı gerçek zamanlı; varsayılan 5 sn broadcast.
"""
import asyncio, json, os, sys, logging, time

ROOT = os.environ.get('MINA_DATA_ROOT', '/root/MINA_v2')
sys.path.insert(0, ROOT)
DASH_DIR = os.path.join(ROOT, 'dashboard')
if DASH_DIR not in sys.path:
    sys.path.insert(0, DASH_DIR)
BROADCAST_SEC = int(os.environ.get('MINA_WS_BROADCAST_SEC', '3'))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

import websockets
from dashboard_auth import validate_login, create_session_token, verify_session_token
from backend.config import BinanceConfig, AccountManager

MERTER_STATE_PATH = os.path.join(ROOT, 'signal_bot/merter_dca_state.json')
_rvol_cache = {}  # symbol -> (value, ts)
_futures_symbols_cache = {"ts": 0.0, "data": []}
_FUTURES_SYMBOLS_TTL = 600

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('mina-ws')

# ── Binance client (singleton) ───────────────────────────────────────────────
_client = None
def get_client():
    global _client
    if _client is None:
        _client = BinanceConfig().get_client()
    return _client

# ── JSON yardımcı ────────────────────────────────────────────────────────────
def read_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

# ── Engine durumu ────────────────────────────────────────────────────────────
def engine_running():
    try:
        with open(os.path.join(ROOT, 'engine.lock')) as f:
            pid = int(f.read().strip())
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False

# ── Log tamponu ─────────────────────────────────────────────────────────────
LOG_PATH     = os.path.join(ROOT, 'mina_bot.log')
_log_buf     = []
_log_pos     = 0

_GHOST_LOG_MARKERS = (
    'HAYALET', 'hayalet', '👻', 'ghost position', 'GHOST PO',
)


def _filter_dashboard_logs(lines: list) -> list:
    """Hayalet pozisyon uyarılarını dashboard log akışından çıkar."""
    out = []
    for line in lines:
        if any(m in line for m in _GHOST_LOG_MARKERS):
            continue
        out.append(line)
    return out

MACRO_LEVELS_PATH = os.path.join(ROOT, 'signal_bot/macro_levels.json')

def get_macro_levels():
    """Makro panel — snippet alanı her zaman dolu/boş string olarak gider."""
    levels: list = []
    try:
        from signal_bot.macro_levels_store import panel_levels_for_dashboard
        levels = panel_levels_for_dashboard()
    except Exception as exc:
        log.warning(f"macro_levels import: {exc}")
        data = read_json(MACRO_LEVELS_PATH)
        levels = data.get('levels') or []

    prices = {}
    try:
        from signal_bot.macro_prices import fetch_macro_prices
        prices = fetch_macro_prices(get_client())
    except Exception as exc:
        log.warning(f"macro_prices: {exc}")

    out = []
    for row in levels:
        item = dict(row)
        snippet = (item.get('snippet') or item.get('text') or '').strip()
        item['snippet'] = snippet
        item['text'] = snippet
        coin = item.get('coin')
        if not coin:
            continue
        px = prices.get(coin) or {}
        item['markPrice'] = px.get('value')
        item['markDisplay'] = px.get('display')
        out.append(item)
    if not out and os.path.isfile(MACRO_LEVELS_PATH):
        log.warning("macro_levels: panel bos — dosya=%s", MACRO_LEVELS_PATH)
    return out

def get_futures_symbols_list():
    """Aktif USDT perpetual semboller — 10 dk cache."""
    now = time.time()
    cached = _futures_symbols_cache.get("data") or []
    if cached and now - float(_futures_symbols_cache.get("ts") or 0) < _FUTURES_SYMBOLS_TTL:
        return cached
    try:
        info = get_client().futures_exchange_info()
        symbols = []
        for s in info.get("symbols", []):
            sym = str(s.get("symbol") or "")
            if not sym.endswith("USDT"):
                continue
            if s.get("status") != "TRADING":
                continue
            ct = s.get("contractType")
            if ct is not None and ct != "PERPETUAL":
                continue
            symbols.append(sym)
        symbols = sorted(set(symbols))
        if not symbols:
            symbols = sorted(
                str(s.get("symbol"))
                for s in info.get("symbols", [])
                if s.get("status") == "TRADING"
                and str(s.get("symbol", "")).endswith("USDT")
            )
        _futures_symbols_cache["ts"] = now
        _futures_symbols_cache["data"] = symbols
        log.info("futures_exchange_info: %s aktif USDT sembol", len(symbols))
        return symbols
    except Exception as exc:
        log.error("futures_exchange_info hatası: %s", exc)
        return cached or []


def _format_manual_open_output(text: str, max_len: int = 4000) -> str:
    """Subprocess çıktısından tam Binance hata satırını önceliklendir."""
    text = (text or "").strip()
    if not text:
        return "Çıktı yok"
    if len(text) <= max_len:
        return text
    for line in reversed(text.splitlines()):
        low = line.lower()
        if any(k in low for k in ("binanceapiexception", "apierror", "red:", "api error", "error code")):
            return line.strip()
    return text[-max_len:]


def _log_manual_open_attempt(
    symbol: str,
    side: str,
    leverage: int,
    entry_price,
    ok: bool,
    output: str = "",
    blocked_reason: str = "",
) -> None:
    """Her manuel açılış denemesini dashboard_ws.log'a yaz."""
    sym = (symbol or "").upper()
    sd = (side or "LONG").upper()
    ep = ""
    if entry_price is not None:
        try:
            ep = f" entry={float(entry_price):.8g}"
        except (TypeError, ValueError):
            ep = f" entry={entry_price}"
    status = "OK" if ok else "FAIL"
    parts = [f"MANUAL_OPEN {status} {sym} {sd} {leverage}x{ep}"]
    if blocked_reason:
        parts.append(f"blocked={blocked_reason}")
    body = (output or "").strip()
    if body:
        parts.append(f"output={body}")
    log.info(" | ".join(parts))


def get_symbol_mark_price(symbol: str) -> float:
    sym = (symbol or "").upper()
    if not sym:
        raise ValueError("symbol gerekli")
    ticker = get_client().futures_mark_price(symbol=sym)
    return float(ticker["markPrice"])


async def send_futures_symbols(websocket):
    await websocket.send(json.dumps({
        "action": "futures_symbols",
        "symbols": get_futures_symbols_list(),
    }))


async def send_mark_price(websocket, symbol: str):
    sym = (symbol or "").upper()
    try:
        price = get_symbol_mark_price(sym)
        await websocket.send(json.dumps({
            "action": "mark_price",
            "symbol": sym,
            "price": price,
        }))
    except Exception as exc:
        await websocket.send(json.dumps({
            "action": "mark_price",
            "symbol": sym,
            "error": str(exc),
        }))

def get_dashboard_settings():
    try:
        from mina_dashboard_settings import load_settings
        return load_settings()
    except Exception as exc:
        log.warning(f"settings: {exc}")
        return {
            "merterTimeStopH": 4,
            "halukTimeStopH": 8,
            "breakevenMult": 1.0020,
            "telegramNotify": True,
            "motorActive": True,
        }

def get_slot_summary_defaults():
    try:
        from mina_slot_policy import SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR, SLOT_TOTAL
        from mina_slot_policy import SLOTS_EI_DCA, SLOTS_MERTER_OTHER_DCA
    except ImportError:
        SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR = 7, 1
        SLOTS_EI_DCA, SLOTS_MERTER_OTHER_DCA = 2, 1
        SLOT_TOTAL = 10
    return {
        'motorUsed': 0,
        'motorMax': SLOTS_HALUK_MOTOR,
        'merterMotorUsed': 0,
        'merterMotorMax': SLOTS_MERTER_MOTOR,
        'merterUsed': 0,
        'merterMax': SLOTS_EI_DCA + SLOTS_MERTER_OTHER_DCA,
        'merterEiMax': SLOTS_EI_DCA,
        'merterOtherMax': SLOTS_MERTER_OTHER_DCA,
        'slotTotal': SLOT_TOTAL,
    }


def get_merter_slots_meta():
    """Merter DCA yuvaları: 2× EI + 1× diğer."""
    try:
        from mina_slot_policy import (
            MERTER_DCA_YUVAS, MERTER_DCA_LABELS, LEGACY_YUVA_MAP,
            MERTER_DCA_FILTER_MODE, MERTER_DCA_FILTER_DESC,
        )
    except ImportError:
        MERTER_DCA_YUVAS = ('merter_ei_1', 'merter_ei_2', 'merter_other')
        MERTER_DCA_LABELS = {
            'merter_ei_1': 'EI #1 — Süzgeçli',
            'merter_ei_2': 'EI #2 — Süzgeçsiz',
            'merter_other': 'Merter Diğer (RSI)',
        }
        MERTER_DCA_FILTER_MODE = {
            'merter_ei_1': 'filtered',
            'merter_ei_2': 'unfiltered',
            'merter_other': 'rsi',
        }
        MERTER_DCA_FILTER_DESC = {
            'merter_ei_1': 'RVOL≥2 + EMA20 + SFP + hacim + pump koruması',
            'merter_ei_2': 'Filtre yok — EI listesinden doğrudan giriş',
            'merter_other': 'RSI<20 + teyit + hacim',
        }
        LEGACY_YUVA_MAP = {'merter_ei': 'merter_ei_1', 'merter_rsi': 'merter_other'}

    state = read_json(MERTER_STATE_PATH)
    positions = dict(state.get('positions') or {})
    for old, new in LEGACY_YUVA_MAP.items():
        if old in positions and new not in positions:
            positions[new] = positions.pop(old)

    slots = {}
    for yuva in MERTER_DCA_YUVAS:
        p = positions.get(yuva) or {}
        slots[yuva] = {
            'yuva': yuva,
            'label': MERTER_DCA_LABELS.get(yuva, yuva),
            'filterMode': MERTER_DCA_FILTER_MODE.get(yuva),
            'filterDesc': MERTER_DCA_FILTER_DESC.get(yuva, ''),
            'occupied': bool(p),
            'symbol': p.get('symbol'),
            'partsFilled': int(p.get('parts_filled') or 0),
            'partsTotal': int(p.get('parts_total') or 10),
            'breakevenMode': bool(p.get('breakeven_mode')),
            'avgPrice': p.get('avg_price'),
        }
    return slots


def calculate_rvol(client, symbol):
    """RVOL = son kapalı 5m hacim / son 1s ortalama 5m hacmi."""
    now = time.time()
    cached = _rvol_cache.get(symbol)
    if cached and now - cached[1] < 30:
        return cached[0]
    try:
        kl = client.futures_klines(symbol=symbol, interval='5m', limit=14)
        closed = kl[:-1]
        if len(closed) < 12:
            return None
        vols = [float(k[7]) for k in closed[-12:]]
        avg = sum(vols) / len(vols)
        if avg <= 0:
            return None
        rvol = float(closed[-1][7]) / avg
        _rvol_cache[symbol] = (round(rvol, 2), now)
        return round(rvol, 2)
    except Exception:
        return None


def get_derr_summary() -> dict:
    """DERR kapalı işlemlerden win rate ve özet istatistik."""
    db_path = os.path.join(ROOT, "mina_trading_journal.db")
    if not os.path.isfile(db_path):
        return {}
    try:
        from mina_trading_journal import TradingJournal

        journal = TradingJournal(db_path=db_path)
        cur = journal.conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) AS winners,
                SUM(CASE WHEN pnl_usdt <= 0 THEN 1 ELSE 0 END) AS losers,
                SUM(pnl_usdt) AS net_pnl,
                AVG(CASE WHEN pnl_usdt > 0 THEN pnl_usdt END) AS avg_profit,
                AVG(CASE WHEN pnl_usdt < 0 THEN pnl_usdt END) AS avg_loss
            FROM trades
            WHERE status = 'closed'
            """
        )
        row = cur.fetchone()
        total = int(row["total"] or 0)
        winners = int(row["winners"] or 0)
        losers = int(row["losers"] or 0)
        net_pnl = float(row["net_pnl"] or 0)
        avg_profit = float(row["avg_profit"] or 0)
        avg_loss = float(row["avg_loss"] or 0)
        win_rate = round(winners / total * 100, 1) if total else 0.0

        cur.execute(
            """
            SELECT symbol, pnl_usdt
            FROM trades
            WHERE status = 'closed'
            ORDER BY pnl_usdt DESC
            LIMIT 1
            """
        )
        best_row = cur.fetchone()
        cur.execute(
            """
            SELECT symbol, pnl_usdt
            FROM trades
            WHERE status = 'closed'
            ORDER BY pnl_usdt ASC
            LIMIT 1
            """
        )
        worst_row = cur.fetchone()

        cur.execute(
            """
            SELECT symbol, SUM(pnl_usdt) AS sym_pnl
            FROM trades
            WHERE status = 'closed'
            GROUP BY symbol
            ORDER BY sym_pnl DESC
            """
        )
        sym_rows = cur.fetchall()
        best = sym_rows[0]["symbol"].replace("USDT", "") if sym_rows else None
        worst = sym_rows[-1]["symbol"].replace("USDT", "") if sym_rows else None
        journal.close()
        best_trade = None
        worst_trade = None
        if best_row and best_row["pnl_usdt"] is not None:
            best_trade = {
                "symbol": str(best_row["symbol"]).replace("USDT", ""),
                "pnl": round(float(best_row["pnl_usdt"]), 2),
            }
        if worst_row and worst_row["pnl_usdt"] is not None:
            worst_trade = {
                "symbol": str(worst_row["symbol"]).replace("USDT", ""),
                "pnl": round(float(worst_row["pnl_usdt"]), 2),
            }
        return {
            "totalTrades": total,
            "winningTrades": winners,
            "losingTrades": losers,
            "winRate": win_rate,
            "netPnl": round(net_pnl, 2),
            "avgProfit": round(avg_profit, 2),
            "avgLoss": round(avg_loss, 2),
            "bestTrade": best_trade,
            "worstTrade": worst_trade,
            "bestCoin": best,
            "worstCoin": worst,
        }
    except Exception as exc:
        log.debug("derr summary: %s", exc)
        return {}


def update_logs():
    global _log_buf, _log_pos
    try:
        size = os.path.getsize(LOG_PATH)
        with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
            if _log_pos == 0:
                lines = f.readlines()
                _log_buf = _filter_dashboard_logs([l.rstrip() for l in lines[-60:] if l.strip()])
                _log_pos = f.seek(0, 2)
            elif size > _log_pos:
                f.seek(_log_pos)
                new = f.read()
                _log_pos = f.tell()
                new_lines = _filter_dashboard_logs([l.rstrip() for l in new.splitlines() if l.strip()])
                _log_buf.extend(new_lines)
                _log_buf = _log_buf[-120:]
    except Exception as e:
        log.debug(f"log update: {e}")


def _binance_open_keys(raw_positions) -> set:
    keys = set()
    for p in raw_positions:
        amt = float(p.get('positionAmt') or 0)
        if amt == 0:
            continue
        sym = p['symbol']
        side = 'LONG' if amt > 0 else 'SHORT'
        keys.add(f"{sym}_{side}")
    return keys


def _prune_stale_tracking(open_keys: set) -> None:
    """Binance'te kapalı pozisyonların tracking kayıtlarını sil."""
    if not open_keys and open_keys is not None:
        pass
    try:
        import mina_tracking as mt
        for fname in mt.TRACKING_FILES:
            data = mt.load_json(fname)
            stale = [k for k in list(data.keys()) if k not in open_keys]
            if stale:
                for k in stale:
                    del data[k]
                mt.save_json(fname, data)
    except Exception as exc:
        log.debug("prune tracking: %s", exc)

# ── Binance veri çekimi ──────────────────────────────────────────────────────
async def get_data():
    try:
        client  = get_client()
        account = AccountManager(client)
        balance = account.get_usdt_balance()
        balance_breakdown = account.get_balance_breakdown()

        btc_mark = None
        try:
            btc_mark = round(float(client.futures_mark_price(symbol='BTCUSDT')['markPrice']), 2)
        except Exception:
            pass

        raw            = client.futures_position_information()
        open_keys      = _binance_open_keys(raw)
        _prune_stale_tracking(open_keys)
        defense_levels = read_json(os.path.join(ROOT, 'defense_levels.json'))
        for stale_key in list(defense_levels.keys()):
            if stale_key not in open_keys:
                defense_levels.pop(stale_key, None)
        try:
            with open(os.path.join(ROOT, 'defense_levels.json'), 'w', encoding='utf-8') as df:
                json.dump(defense_levels, df, indent=2)
                df.write('\n')
        except OSError:
            pass
        merter_slots   = get_merter_slots_meta()
        try:
            from mina_signal_source import SOURCE_LABELS, get_position_sources
            position_sources = get_position_sources()
        except ImportError:
            SOURCE_LABELS = {"HT": "Haluk Hoca", "MZ": "Merter", "MANUEL": "Manuel"}
            position_sources = read_json(os.path.join(ROOT, 'position_sources.json'))
        try:
            from mina_slot_policy import SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR, SLOT_TOTAL
            from mina_slot_policy import SLOTS_EI_DCA, SLOTS_MERTER_OTHER_DCA
        except ImportError:
            SLOTS_HALUK_MOTOR, SLOTS_MERTER_MOTOR = 7, 1
            SLOTS_EI_DCA, SLOTS_MERTER_OTHER_DCA = 2, 1
            SLOT_TOTAL = 10

        merter_by_sym  = {
            s['symbol']: yuva
            for yuva, s in merter_slots.items()
            if s.get('occupied') and s.get('symbol')
        }

        positions = []
        for p in raw:
            amt = float(p['positionAmt'])
            if amt == 0: continue

            sym     = p['symbol']
            side    = 'LONG' if amt > 0 else 'SHORT'
            pos_key = f"{sym}_{side}"
            entry   = float(p['entryPrice'])
            mark    = float(p.get('markPrice', 0))
            upnl    = float(p['unRealizedProfit'])
            liq     = float(p.get('liquidationPrice', 0))
            lev     = int(p['leverage'])
            iso_m   = float(p.get('isolatedMargin', 0))

            init_m = iso_m if iso_m > 0 else (abs(amt) * entry / lev)
            roe    = (upnl / init_m * 100) if init_m > 0 else 0
            pnl_pct = ((mark - entry) / entry * 100) if side == 'LONG' and entry else \
                      ((entry - mark) / entry * 100) if entry else 0

            is_merter = sym in merter_by_sym and lev == 1 and side == 'LONG'
            rvol = calculate_rvol(client, sym)
            src_code = position_sources.get(pos_key)
            if is_merter and not src_code:
                src_code = 'MZ'

            positions.append({
                'symbol':       sym,
                'side':         side,
                'leverage':     lev,
                'entryPrice':   entry,
                'markPrice':    mark,
                'amount':       abs(amt),
                'pnlUSDT':      upnl,
                'pnlPct':       pnl_pct,
                'roe':          roe,
                'liqPrice':     liq,
                'margin':       iso_m,
                'defenseLevel': defense_levels.get(pos_key, 0),
                'posKey':       pos_key,
                'slotType':     'merter' if is_merter else 'motor',
                'merterYuva':   merter_by_sym.get(sym),
                'rvol':         rvol,
                'signalSource': src_code,
                'signalSourceLabel': SOURCE_LABELS.get(src_code, src_code) if src_code else None,
            })

        motor_positions  = [p for p in positions if p['slotType'] == 'motor']
        merter_positions = [p for p in positions if p['slotType'] == 'merter']
        merter_used      = sum(1 for s in merter_slots.values() if s['occupied'])

        update_logs()

        derr = get_derr_summary()

        risk_status = {}
        daily_pnl = 0.0
        try:
            from datetime import date
            from mina_dashboard_settings import (
                daily_loss_limit_pct,
                load_daily_risk_state,
                is_new_entries_blocked,
            )
            from mina_trading_journal import TradingJournal

            risk_status = load_daily_risk_state()
            today = date.today().isoformat()
            if risk_status.get("date") != today:
                balance_risk = balance
                limit_pct = daily_loss_limit_pct()
                limit_usdt = -(balance_risk * limit_pct / 100.0)
                half_usdt = limit_usdt / 2.0
                db_path = os.path.join(ROOT, "mina_trading_journal.db")
                journal = TradingJournal(db_path=db_path)
                today_pnl = journal.get_today_realized_pnl()
                journal.close()
                level = "ok"
                if today_pnl <= limit_usdt:
                    level = "kill"
                elif today_pnl <= half_usdt:
                    level = "warn"
                risk_status = {
                    "date": today,
                    "today_pnl": round(today_pnl, 2),
                    "balance": round(balance_risk, 2),
                    "limit_pct": limit_pct,
                    "limit_usdt": round(limit_usdt, 2),
                    "half_usdt": round(half_usdt, 2),
                    "level": level,
                }
            daily_pnl = float(risk_status.get("today_pnl") or 0)
            risk_status["newEntriesBlocked"] = is_new_entries_blocked()
        except Exception as exc:
            log.debug(f"risk_status: {exc}")

        return {
            'balance':         balance,
            'balanceBreakdown': balance_breakdown,
            'btcMarkPrice':    btc_mark,
            'floatingPnl':     sum(p['pnlUSDT'] for p in positions),
            'dailyPnl':        daily_pnl,
            'riskStatus':      risk_status,
            'positionCount':   len(positions),
            'motorCount':      len(motor_positions),
            'merterCount':     len(merter_positions),
            'engineRunning':   engine_running(),
            'motorPaused':     not get_dashboard_settings().get('motorActive', True),
            'settings':        get_dashboard_settings(),
            'positions':       positions,
            'motorPositions':  motor_positions,
            'merterPositions': merter_positions,
            'merterSlots':     merter_slots,
            'macroLevels':     get_macro_levels(),
            'halukPdfTimestamp': read_json(os.path.join(ROOT, 'signal_bot/raw_signal_queue.json')).get('haluk_pdf_timestamp'),
            'slotSummary': {
                'motorUsed':  len(motor_positions),
                'motorMax':   SLOTS_HALUK_MOTOR,
                'merterMotorUsed': len(motor_positions),  # 4x motor subset
                'merterMotorMax': SLOTS_MERTER_MOTOR,
                'merterUsed': merter_used,
                'merterMax':  SLOTS_EI_DCA + SLOTS_MERTER_OTHER_DCA,
                'merterEiMax': SLOTS_EI_DCA,
                'merterOtherMax': SLOTS_MERTER_OTHER_DCA,
                'slotTotal': SLOT_TOTAL,
            },
            'logs':            list(_log_buf),
            'derr':            derr,
            'winRate':         derr.get('winRate'),
            'totalTrades':     derr.get('totalTrades'),
            'winningTrades':   derr.get('winningTrades'),
        }
    except Exception as e:
        log.error(f"get_data: {e}")
        return {
            'error': str(e),
            'positions': [],
            'logs': list(_log_buf),
            'macroLevels': get_macro_levels(),
            'settings': get_dashboard_settings(),
            'slotSummary': get_slot_summary_defaults(),
            'engineRunning': engine_running(),
            'motorPaused': not get_dashboard_settings().get('motorActive', True),
        }

async def update_dashboard_settings(websocket, settings):
    try:
        from mina_dashboard_settings import save_settings
        saved = save_settings(settings or {})
        log.info(
            "SETTINGS_SAVED merterTimeStopH=%s halukTimeStopH=%s dailyLossLimitPct=%s breakevenMult=%s motorActive=%s",
            saved.get("merterTimeStopH"),
            saved.get("halukTimeStopH"),
            saved.get("dailyLossLimitPct"),
            saved.get("breakevenMult"),
            saved.get("motorActive"),
        )
        await websocket.send(json.dumps({'action': 'settings_saved', 'settings': saved}))
    except Exception as e:
        log.error("SETTINGS_SAVE_FAIL: %s", e)
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

def _reconcile_derr_sync() -> int:
    """Binance vs DERR hayalet kapatma (blocking — executor'da çalıştır)."""
    try:
        from mina_position_manager import MinaPositionManager
        from mina_trading_journal import TradingJournal

        client = get_client()
        account = AccountManager(client)
        slot = account.calculate_slot_size()
        db_path = os.path.join(ROOT, 'mina_trading_journal.db')
        journal = TradingJournal(db_path=db_path)
        mina = MinaPositionManager(client, slot, journal=journal, data_root=ROOT)
        closed = mina.reconcile_derr_with_binance(verbose=False)
        journal.close()
        if closed:
            log.info("DERR reconcile (WS): %s kayit kapandi", len(closed))
        return len(closed)
    except Exception as exc:
        log.warning("DERR reconcile (WS): %s", exc)
        return 0

async def push_broadcast():
    """Bağlı tüm istemcilere anında güncel Binance snapshot gönder."""
    if not CONNECTED:
        return
    try:
        data = await get_data()
        msg = json.dumps(data)
        dead = set()
        for ws in list(CONNECTED):
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        CONNECTED.difference_update(dead)
    except Exception as e:
        log.error(f"push_broadcast: {e}")

# ── Tek pozisyon kapat ───────────────────────────────────────────────────────
async def close_position(websocket, symbol, side):
    try:
        if not symbol or not side:
            raise ValueError('symbol and side required')
        client = get_client()
        raw = client.futures_position_information(symbol=symbol)
        closed = False
        for p in raw:
            amt = float(p['positionAmt'])
            if amt == 0:
                continue
            pos_side = 'LONG' if amt > 0 else 'SHORT'
            if pos_side != side:
                continue
            c_side = 'SELL' if amt > 0 else 'BUY'
            qty = abs(amt)
            client.futures_create_order(
                symbol=symbol, side=c_side, type='MARKET',
                quantity=qty, positionSide=side)
            closed = True
            log.warning(f"Client closed: {symbol} {side} qty={qty}")
            break
        if closed:
            await asyncio.to_thread(_reconcile_derr_sync)
            raw_all = client.futures_position_information()
            _prune_stale_tracking(_binance_open_keys(raw_all))
        await websocket.send(json.dumps({
            'action': 'close_position_result',
            'symbol': symbol, 'side': side, 'closed': closed,
        }))
        await push_broadcast()
    except Exception as e:
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

# ── Panik: tüm pozisyonları kapat ───────────────────────────────────────────
async def close_all(websocket):
    try:
        client = get_client()
        raw    = client.futures_position_information()
        closed = 0
        for p in raw:
            amt = float(p['positionAmt'])
            if amt == 0: continue
            sym   = p['symbol']
            side  = 'LONG' if amt > 0 else 'SHORT'
            c_side = 'SELL' if amt > 0 else 'BUY'
            try:
                client.futures_create_order(
                    symbol=sym, side=c_side, type='MARKET',
                    quantity=abs(amt), positionSide=side)
                closed += 1
                log.warning(f"PANIC closed: {sym} {side}")
            except Exception as e:
                log.error(f"close error {sym}: {e}")
        await asyncio.to_thread(_reconcile_derr_sync)
        await websocket.send(json.dumps({'action': 'close_all_result', 'closed': closed}))
        await push_broadcast()
    except Exception as e:
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

async def manual_open_position(
    websocket, symbol, side, leverage=4, entry_price=None, order_type=None, stop_price=None
):
    """Dashboard / WS üzerinden manuel motor girişi."""
    allowed_leverages = {1, 2, 3, 4, 5, 10}
    sym = (symbol or '').upper()
    sd = (side or 'LONG').upper()
    lev = int(leverage or 4)
    try:
        from mina_dashboard_settings import is_motor_paused, is_new_entries_blocked
        if is_motor_paused():
            out = 'Motor pasif (dashboard ayarları)'
            _log_manual_open_attempt(sym, sd, lev, entry_price, False, out, 'motor_paused')
            await websocket.send(json.dumps({
                'action': 'manual_open_result',
                'ok': False,
                'symbol': sym,
                'side': sd,
                'output': out,
            }))
            return
        if is_new_entries_blocked():
            out = 'Günlük zarar limiti aşıldı — yeni pozisyon açılamaz'
            _log_manual_open_attempt(sym, sd, lev, entry_price, False, out, 'daily_loss_kill')
            await websocket.send(json.dumps({
                'action': 'manual_open_result',
                'ok': False,
                'symbol': sym,
                'side': sd,
                'output': out,
            }))
            return
        import subprocess
        if lev not in allowed_leverages:
            out = f'Geçersiz kaldıraç {lev}x — izin verilen: 1, 2, 3, 4, 5, 10'
            _log_manual_open_attempt(sym, sd, lev, entry_price, False, out, 'invalid_leverage')
            await websocket.send(json.dumps({
                'action': 'manual_open_result',
                'ok': False,
                'symbol': sym,
                'side': sd,
                'output': out,
            }))
            return
        cmd = [
            os.path.join(ROOT, 'venv/bin/python'),
            os.path.join(ROOT, 'scripts/manual_open.py'),
            '--symbol', sym,
            '--side', sd,
            '--leverage', str(lev),
            '--source', 'haluk',
        ]
        ot = (order_type or 'market').lower().replace(' ', '_')
        if ot in ('stop_market', 'stop'):
            cmd.extend(['--order-type', 'stop_market'])
            if stop_price is not None:
                try:
                    sp = float(stop_price)
                    if sp > 0:
                        cmd.extend(['--stop-price', str(sp)])
                except (TypeError, ValueError):
                    pass
        elif ot == 'limit':
            cmd.extend(['--order-type', 'limit'])
            if entry_price is not None:
                try:
                    ep = float(entry_price)
                    if ep > 0:
                        cmd.extend(['--entry-price', str(ep)])
                except (TypeError, ValueError):
                    pass
        else:
            cmd.extend(['--order-type', 'market'])
            if entry_price is not None:
                try:
                    ep = float(entry_price)
                    if ep > 0:
                        cmd.extend(['--entry-price', str(ep)])
                except (TypeError, ValueError):
                    pass
        log.info(
            "MANUAL_OPEN START %s %s %sx type=%s entry=%s stop=%s",
            sym, sd, lev, ot, entry_price, stop_price,
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=ROOT)
        raw_out = (proc.stdout or '') + (proc.stderr or '')
        formatted = _format_manual_open_output(raw_out)
        ok = proc.returncode == 0
        _log_manual_open_attempt(sym, sd, lev, entry_price, ok, raw_out.strip())
        await websocket.send(json.dumps({
            'action': 'manual_open_result',
            'ok': ok,
            'symbol': sym,
            'side': sd,
            'output': formatted,
        }))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log_manual_open_attempt(sym, sd, lev, entry_price, False, f"{type(e).__name__}: {e}\n{tb}", 'exception')
        log.error("MANUAL_OPEN exception %s %s: %s", sym, sd, e)
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

async def send_haluk_archive(websocket, msg: dict):
    try:
        from signal_bot.haluk_message_store import query_haluk_messages
        result = query_haluk_messages(
            coin=msg.get('coin'),
            message_type=msg.get('messageType'),
            date_from=msg.get('dateFrom'),
            date_to=msg.get('dateTo'),
            limit=int(msg.get('limit') or 50),
            offset=int(msg.get('offset') or 0),
        )
        await websocket.send(json.dumps({
            'action': 'haluk_archive',
            'total': result.get('total', 0),
            'items': result.get('items', []),
        }))
    except Exception as e:
        log.error(f"haluk_archive: {e}")
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))


async def send_upbit_listings(websocket, msg: dict):
    try:
        from signal_bot.haluk_message_store import query_upbit_listings
        result = query_upbit_listings(limit=int(msg.get('limit') or 300), client=get_client())
        await websocket.send(json.dumps({
            'action': 'upbit_listings',
            'total': result.get('total', 0),
            'items': result.get('items', []),
            'coins': result.get('coins', []),
        }))
    except Exception as e:
        log.error(f"upbit_listings: {e}")
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))


async def send_binance_new_listings(websocket, msg: dict):
    try:
        from signal_bot.binance_listings import get_cached_listings
        force = bool(msg.get('forceRefresh'))
        result = get_cached_listings(force_refresh=force)
        await websocket.send(json.dumps({
            'action': 'binance_new_listings',
            'total': result.get('total', 0),
            'coins': result.get('coins', []),
            'updatedAt': result.get('updatedAtDisplay') or result.get('updatedAt'),
            'days': result.get('days', 50),
        }))
    except Exception as e:
        log.error(f"binance_new_listings: {e}")
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))


async def send_upbit_trader_status(websocket, msg: dict):
    try:
        from signal_bot.upbit_listing_trader import get_dashboard_status
        result = get_dashboard_status()
        await websocket.send(json.dumps({
            'action': 'upbit_trader_status',
            **result,
        }))
    except Exception as e:
        log.error(f"upbit_trader_status: {e}")
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

# ── WebSocket handler ────────────────────────────────────────────────────────
CONNECTED = set()

def _is_authenticated(websocket) -> bool:
    return bool(getattr(websocket, 'authenticated', False))


async def _send_full_snapshot(websocket):
    data = await get_data()
    await websocket.send(json.dumps(data))
    await send_futures_symbols(websocket)


async def handler(websocket):
    websocket.authenticated = False
    websocket.auth_user = None
    CONNECTED.add(websocket)
    log.info(f"+ client ({len(CONNECTED)} total)")
    try:
        await websocket.send(json.dumps({'action': 'auth_required'}))
    except Exception as exc:
        log.error("handler auth_required: %s", exc)

    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                action = msg.get('action')

                if action == 'login':
                    username = (msg.get('username') or '').strip()
                    password = msg.get('password') or ''
                    if validate_login(username, password):
                        session = create_session_token(username)
                        websocket.authenticated = True
                        websocket.auth_user = username
                        await websocket.send(json.dumps({'action': 'login_ok', **session}))
                        await _send_full_snapshot(websocket)
                    else:
                        await websocket.send(json.dumps({
                            'action': 'login_failed',
                            'error': 'Kullanıcı adı veya şifre hatalı',
                        }))
                    continue

                if action == 'auth':
                    ok, user = verify_session_token(msg.get('token') or '')
                    if ok:
                        websocket.authenticated = True
                        websocket.auth_user = user
                        await websocket.send(json.dumps({'action': 'auth_ok', 'user': user}))
                        await _send_full_snapshot(websocket)
                    else:
                        await websocket.send(json.dumps({
                            'action': 'auth_failed',
                            'error': 'Geçersiz veya süresi dolmuş oturum',
                        }))
                    continue

                if action == 'logout':
                    websocket.authenticated = False
                    websocket.auth_user = None
                    await websocket.send(json.dumps({'action': 'logged_out'}))
                    continue

                if not _is_authenticated(websocket):
                    await websocket.send(json.dumps({
                        'action': 'auth_required',
                        'error': 'Oturum gerekli',
                    }))
                    continue

                if action == 'close_all':
                    log.warning("PANIC triggered by client!")
                    await close_all(websocket)
                elif msg.get('action') == 'get_futures_symbols':
                    await send_futures_symbols(websocket)
                elif msg.get('action') == 'get_mark_price':
                    await send_mark_price(websocket, msg.get('symbol'))
                elif msg.get('action') == 'close_position':
                    await close_position(websocket, msg.get('symbol'), msg.get('side'))
                elif msg.get('action') == 'manual_open':
                    await manual_open_position(
                        websocket,
                        msg.get('symbol'),
                        msg.get('side'),
                        msg.get('leverage', 4),
                        msg.get('entryPrice'),
                        msg.get('orderType'),
                        msg.get('stopPrice'),
                    )
                elif msg.get('action') == 'update_settings':
                    await update_dashboard_settings(websocket, msg.get('settings'))
                elif msg.get('action') == 'get_haluk_archive':
                    await send_haluk_archive(websocket, msg)
                elif msg.get('action') == 'get_upbit_listings':
                    await send_upbit_listings(websocket, msg)
                elif msg.get('action') == 'get_binance_new_listings':
                    await send_binance_new_listings(websocket, msg)
                elif msg.get('action') == 'get_upbit_trader_status':
                    await send_upbit_trader_status(websocket, msg)
            except Exception as e:
                log.error(f"handler msg: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED.discard(websocket)
        log.info(f"- client ({len(CONNECTED)} total)")

# ── Broadcast döngüsü ───────────────────────────────────────────────────────
async def broadcast_loop():
    global CONNECTED
    while True:
        await asyncio.sleep(BROADCAST_SEC)
        if not CONNECTED: continue
        try:
            data = await get_data()
            msg  = json.dumps(data)
            dead = set()
            for ws in list(CONNECTED):
                if not _is_authenticated(ws):
                    continue
                try:    await ws.send(msg)
                except: dead.add(ws)
            CONNECTED.difference_update(dead)
        except Exception as e:
            log.error(f"broadcast: {e}")

# ── Main ─────────────────────────────────────────────────────────────────────
async def main():
    log.info("MINA v2 WebSocket server starting on :8765")
    async with websockets.serve(handler, '0.0.0.0', 8765):
        log.info("Ready — ws://0.0.0.0:8765")
        await broadcast_loop()

if __name__ == '__main__':
    asyncio.run(main())
