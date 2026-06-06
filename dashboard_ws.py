#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MINA v2 — Dashboard WebSocket Server  port 8765
5 sn'de bir Binance verisi + log akışı yayınlar.
"""
import asyncio, json, os, sys, logging
sys.path.insert(0, '/root/MINA_v2')

import websockets
from backend.config import BinanceConfig, AccountManager

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
            })

        update_logs()

        return {
            'balance':       balance,
            'floatingPnl':   sum(p['pnlUSDT'] for p in positions),
            'positionCount': len(positions),
            'engineRunning': engine_running(),
            'positions':     positions,
            'logs':          list(_log_buf),
        }
    except Exception as e:
        log.error(f"get_data: {e}")
        return {'error': str(e), 'positions': [], 'logs': list(_log_buf)}

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
