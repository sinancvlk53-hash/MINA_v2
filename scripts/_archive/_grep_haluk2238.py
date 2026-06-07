#!/usr/bin/env python3
import re
path = "/root/MINA_v2/signal_bot/signals_log.txt"
for l in open(path, encoding="utf-8", errors="replace"):
    if "[HALUK]" not in l:
        continue
    if re.search(r"22:3[0-9]|19:3[4-9]", l):
        print(l.rstrip()[:600])
