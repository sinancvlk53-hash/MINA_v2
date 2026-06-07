#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/root/MINA_v2')
import dashboard.dashboard_ws as ws

async def main():
    d = await ws.get_data()
    if 'error' in d:
        print('ERROR:', d['error'])
    print('motorCount', d.get('motorCount'))
    print('merterCount', d.get('merterCount'))
    print('slotSummary', d.get('slotSummary'))
    if d.get('motorPositions'):
        print('sample rvol', d['motorPositions'][0].get('symbol'), d['motorPositions'][0].get('rvol'))

asyncio.run(main())
