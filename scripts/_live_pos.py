# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
from config import BinanceConfig
c = BinanceConfig().get_client()
positions = c.futures_position_information()
open_pos = [p for p in positions if float(p['positionAmt']) != 0]
print(f'Acik: {len(open_pos)}')
for p in open_pos:
    side = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    sym  = p['symbol']
    lev  = p['leverage']
    ep   = p['entryPrice']
    pnl  = p['unRealizedProfit']
    liq  = p['liquidationPrice']
    mrg  = p['isolatedMargin']
    amt  = p['positionAmt']
    print(f'{sym}|{side}|{lev}x|entry={ep}|pnl={pnl}|liq={liq}|margin={mrg}|amt={amt}')
