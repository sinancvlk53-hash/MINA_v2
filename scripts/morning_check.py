#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabah kontrol — dashboard WS (8765), kimlik bilgisi gerektirmez."""
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("pip install websockets")
    sys.exit(1)

WS_URL = "ws://178.105.150.40:8765"


async def main():
    async with websockets.connect(WS_URL, open_timeout=15) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=20)
        data = json.loads(raw)

    engine = data.get("engineRunning", False)
    balance = data.get("balance")
    pos_count = data.get("positionCount", len(data.get("positions", [])))
    logs = data.get("logs", [])
    last10 = logs[-10:] if logs else []

    print("=== MINA Sabah Kontrol (WebSocket) ===")
    print(f"Motor (engine.lock): {'ÇALIŞIYOR' if engine else 'DURMUŞ / lock yok'}")
    print(f"Bakiye (USDT):       {balance}")
    print(f"Açık pozisyon:       {pos_count}")
    print()
    print("--- Son 10 log satırı ---")
    if last10:
        for line in last10:
            print(line)
    else:
        print("(log yok veya WS log tamponu boş)")
    print()
    if data.get("error"):
        print("WS hata:", data["error"])
    if data.get("positions"):
        print("--- Pozisyon özeti ---")
        for p in data["positions"][:15]:
            print(
                f"  {p['symbol']} {p['side']} {p['leverage']}x "
                f"PnL={p.get('pnlUSDT', 0):.2f} ROE={p.get('roe', 0):.1f}%"
            )


if __name__ == "__main__":
    asyncio.run(main())
