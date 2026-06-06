#!/usr/bin/env python3
import json
import os
import sys
sys.path.insert(0, "/root/MINA_v2")
from signal_bot.binance_listings import get_cached_listings, load_known
d = get_cached_listings()
print("cache total:", d.get("total"), "updated:", d.get("updatedAtDisplay"))
for row in (d.get("coins") or [])[:5]:
    print(row["coin"], row.get("listedAt"), row.get("priceChangePct"))
k = load_known()
print("known seeded:", k.get("seeded"), "symbols:", len(k.get("symbols") or []))
