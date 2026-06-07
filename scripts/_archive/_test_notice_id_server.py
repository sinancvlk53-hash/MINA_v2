#!/usr/bin/env python3
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")
h = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://upbit.com",
    "Referer": "https://upbit.com/service_center/notice",
}
for nid in [7000, 6800, 6500, 6200]:
    r = requests.get(f"https://api-manager.upbit.com/api/v1/notices/{nid}", headers=h, timeout=20)
    print(nid, r.status_code, r.text[:300])
    print("---")
