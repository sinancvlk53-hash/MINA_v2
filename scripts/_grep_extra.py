#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path("/root/MINA_v2/signal_bot")

print("=== merter_dca.log 10:00 ===")
for l in (ROOT / "merter_dca.log").read_text(encoding="utf-8", errors="replace").splitlines():
    if "2026-06-04T10:0" in l:
        print(l)

print("\n=== signals_log HALUK 19:3x / 22:3x ===")
for l in (ROOT / "signals_log.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    if "[HALUK]" not in l or "2026-06-04" not in l:
        continue
    if re.search(r"19:3[0-9]|22:3[0-9]", l):
        print(l[:500])

print("\n=== AL vs SAT scan count (unique msg id) ===")
ids_al = set()
ids_sat = set()
for l in (ROOT / "signals_log.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    if "2026-06-04" not in l or "Sinyal Taraması" not in l:
        continue
    m = re.search(r"id=(\d+)", l)
    if not m:
        continue
    mid = m.group(1)
    if "Yeni AL Sinyalleri" in l:
        ids_al.add(mid)
    elif "Yeni SAT Sinyalleri" in l and "Yeni AL Sinyalleri" not in l:
        ids_sat.add(mid)
print(f"Unique AL scans: {len(ids_al)}")
print(f"Unique SAT-only scans: {len(ids_sat)}")
