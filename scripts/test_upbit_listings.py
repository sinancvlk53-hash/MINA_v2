#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from backend.config import BinanceConfig
from signal_bot.haluk_message_store import query_upbit_listings

r = query_upbit_listings(limit=3, client=BinanceConfig().get_client())
print("msgs", r["total"], "coins", len(r["coins"]))
for row in r["coins"][:10]:
    print(
        row["coin"],
        (row.get("firstMention") or "")[:16],
        row.get("mentionCount"),
        row.get("priceChangePct"),
    )
