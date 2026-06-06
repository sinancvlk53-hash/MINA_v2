#!/usr/bin/env python3
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MINA_DATA_ROOT", "/root/MINA_v2")

from dashboard.dashboard_ws import get_macro_levels

lv = get_macro_levels()
filled = [x for x in lv if (x.get("snippet") or "").strip()]
print("count", len(lv), "filled", len(filled))
print(json.dumps(filled[:4], ensure_ascii=False, indent=2))
