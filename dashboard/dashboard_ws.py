#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MINA v2 — Dashboard WebSocket Server  port 8765
5 sn'de bir Binance verisi + log akışı yayınlar.
"""
import asyncio, json, os, sys, logging, time
sys.path.insert(0, '/root/MINA_v2')

import websockets
from backend.config import BinanceConfig, AccountManager

MERTER_STATE_PATH = '/root/MINA_v2/signal_bot/merter_dca_state.json'
_rvol_cache = {}  # symbol -> (value, ts)

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
        with open(path) as f: return json.load(f)
    except Exception: return {}

# ── Engine durumu ────────────────────────────────────────────────────────────
def engine_running():
    try:
        with open('/root/MINA_v2/engine.lock') as f:
            pid = int(f.read().strip())
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False

# ── Log tamponu ─────────────────────────────────────────────────────────────
LOG_PATH     = '/root/MINA_v2/mina_bot.log'
_log_buf     = []
_log_pos     = 0

MACRO_LEVELS_PATH = '/root/MINA_v2/signal_bot/macro_levels.json'

def get_macro_levels():
    levels: list = []
    try:
        sys.path.insert(0, '/root/MINA_v2')
        from signal_bot.macro_levels_store import panel_levels_for_dashboard
        levels = panel_levels_for_dashboard()
    except Exception as exc:
        log.warning(f"macro_levels: {exc}")
        data = read_json(MACRO_LEVELS_PATH)
        levels = data.get('levels') or []

    out = []
    for row in levels:
        item = dict(row)
        if not item.get('snippet') and item.get('text'):
            item['snippet'] = item['text']
        out.append(item)
    return out

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


def update_logs():
    global _log_buf, _log_pos
    try:
        size = os.path.getsize(LOG_PATH)
        with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
            if _log_pos == 0:
                lines = f.readlines()
                _log_buf = [l.rstrip() for l in lines[-60:] if l.strip()]
                _log_pos = f.seek(0, 2)
            elif size > _log_pos:
                f.seek(_log_pos)
                new = f.read()
                _log_pos = f.tell()
                new_lines = [l.rstrip() for l in new.splitlines() if l.strip()]
                _log_buf.extend(new_lines)
                _log_buf = _log_buf[-120:]
    except Exception as e:
        log.debug(f"log update: {e}")

# ── Binance veri çekimi ──────────────────────────────────────────────────────
async def get_data():
    try:
        client  = get_client()
        account = AccountManager(client)
        balance = account.get_usdt_balance()

        raw            = client.futures_position_information()
        defense_levels = read_json('/root/MINA_v2/defense_levels.json')
        merter_slots   = get_merter_slots_meta()
        try:
            from mina_signal_source import SOURCE_LABELS, get_position_sources
            position_sources = get_position_sources()
        except ImportError:
            SOURCE_LABELS = {"HT": "Haluk Hoca", "MZ": "Merter", "MANUEL": "Manuel"}
            position_sources = read_json('/root/MINA_v2/position_sources.json')
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

        return {
            'balance':         balance,
            'floatingPnl':     sum(p['pnlUSDT'] for p in positions),
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
            'halukPdfTimestamp': read_json('/root/MINA_v2/signal_bot/raw_signal_queue.json').get('haluk_pdf_timestamp'),
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
        await websocket.send(json.dumps({'action': 'settings_saved', 'settings': saved}))
    except Exception as e:
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

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
        await websocket.send(json.dumps({
            'action': 'close_position_result',
            'symbol': symbol, 'side': side, 'closed': closed,
        }))
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
        await websocket.send(json.dumps({'action': 'close_all_result', 'closed': closed}))
    except Exception as e:
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

async def manual_open_position(websocket, symbol, side, leverage=4, entry_price=None):
    """Dashboard / WS üzerinden manuel motor girişi."""
    try:
        from mina_dashboard_settings import is_motor_paused
        if is_motor_paused():
            await websocket.send(json.dumps({
                'action': 'manual_open_result',
                'ok': False,
                'symbol': (symbol or '').upper(),
                'side': (side or 'LONG').upper(),
                'output': 'Motor pasif (dashboard ayarları)',
            }))
            return
        import subprocess
        sym = (symbol or '').upper()
        sd = (side or 'LONG').upper()
        lev = int(leverage or 4)
        cmd = [
            '/root/MINA_v2/venv/bin/python',
            '/root/MINA_v2/scripts/manual_open.py',
            '--symbol', sym,
            '--side', sd,
            '--leverage', str(lev),
            '--source', 'haluk',
        ]
        if entry_price is not None:
            try:
                ep = float(entry_price)
                if ep > 0:
                    cmd.extend(['--entry-price', str(ep)])
            except (TypeError, ValueError):
                pass
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd='/root/MINA_v2')
        out = (proc.stdout or '') + (proc.stderr or '')
        ok = proc.returncode == 0
        await websocket.send(json.dumps({
            'action': 'manual_open_result',
            'ok': ok,
            'symbol': sym,
            'side': sd,
            'output': out.strip()[-500:],
        }))
    except Exception as e:
        await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))

# ── WebSocket handler ────────────────────────────────────────────────────────
CONNECTED = set()

async def handler(websocket):
    CONNECTED.add(websocket)
    log.info(f"+ client ({len(CONNECTED)} total)")
    # İlk bağlantıda hemen veri gönder
    try:
        data = await get_data()
        await websocket.send(json.dumps(data))
    except Exception: pass

    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg.get('action') == 'close_all':
                    log.warning("PANIC triggered by client!")
                    await close_all(websocket)
                elif msg.get('action') == 'close_position':
                    await close_position(websocket, msg.get('symbol'), msg.get('side'))
                elif msg.get('action') == 'manual_open':
                    await manual_open_position(
                        websocket,
                        msg.get('symbol'),
                        msg.get('side'),
                        msg.get('leverage', 4),
                        msg.get('entryPrice'),
                    )
                elif msg.get('action') == 'update_settings':
                    await update_dashboard_settings(websocket, msg.get('settings'))
            except Exception as e:
                log.error(f"handler msg: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED.discard(websocket)
        log.info(f"- client ({len(CONNECTED)} total)")

# ── Broadcast döngüsü (5 sn) ────────────────────────────────────────────────
async def broadcast_loop():
    global CONNECTED
    while True:
        await asyncio.sleep(5)
        if not CONNECTED: continue
        try:
            data = await get_data()
            msg  = json.dumps(data)
            dead = set()
            for ws in list(CONNECTED):
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
