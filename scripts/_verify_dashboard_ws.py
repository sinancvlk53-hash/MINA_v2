#!/usr/bin/env python3
import asyncio, json, websockets

async def main():
    async with websockets.connect('ws://178.105.150.40:8765', open_timeout=10) as ws:
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        print('motorCount:', d.get('motorCount'))
        print('merterCount:', d.get('merterCount'))
        print('slotSummary:', d.get('slotSummary'))
        print('merterSlots:', json.dumps(d.get('merterSlots'), indent=2, ensure_ascii=False))
        for p in (d.get('motorPositions') or [])[:3]:
            print(f"  motor {p['symbol']} rvol={p.get('rvol')}")

asyncio.run(main())
