#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZROUSDT bekleyen DCA limit emirlerini iptal et."""
import sys
sys.path.insert(0, "/root/MINA_v2")
from backend.config import BinanceConfig

client = BinanceConfig().get_client()
symbol = "ZROUSDT"
orders = client.futures_get_open_orders(symbol=symbol)
print(f"Açık emir sayısı: {len(orders)}")
for o in orders:
    print(f"  {o['orderId']} {o['type']} {o['side']} price={o['price']} qty={o['origQty']}")
    if o.get("type") == "LIMIT" and o.get("side") == "BUY":
        r = client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
        print(f"  İPTAL OK orderId={o['orderId']} status={r.get('status')}")
remaining = client.futures_get_open_orders(symbol=symbol)
print(f"Kalan açık emir: {len(remaining)}")
