#!/usr/bin/env python3
import sys
sys.path.insert(0, "/root/MINA_v2")
from mina_dashboard_settings import leverage_strategy_mode, load_settings
print("settings", load_settings().get("leverageStrategy"))
for lev in [2,4,5]:
    print(lev, leverage_strategy_mode(lev))
