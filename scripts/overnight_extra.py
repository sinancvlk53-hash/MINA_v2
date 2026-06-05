#!/usr/bin/env python3
import json, sqlite3, subprocess, os

ROOT = "/root/MINA_v2"

print("=== Merter MOVR/TP gece ===")
p = subprocess.run(
    ["grep", "-E", "MOVR|TP1|TP2|KAPAT|Trailing|BTCUSDT", f"{ROOT}/signal_bot/merter_dca.log"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
lines = [l for l in p.stdout.splitlines() if "2026-06-04T2" in l or "2026-06-05T" in l]
for l in lines[-25:]:
    print(l)

print("\n=== mina_bot MOVR/BTC/defense gece ===")
p2 = subprocess.run(
    ["grep", "-E", r"2026-06-04 2[2-9]|2026-06-05 0[0-9]|2026-06-05 10", f"{ROOT}/mina_bot.log"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
for l in p2.stdout.splitlines():
    if any(x in l.upper() for x in ("MOVR", "BTC", "DEFENSE", "D1", "D2", "D3", "HARD", "TP", "TRAIL")):
        print(l)

print("\n=== Journal MOVR/ALGO/BTC ===")
conn = sqlite3.connect(f"{ROOT}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
for r in conn.execute(
    "SELECT id,symbol,side,leverage,open_time,close_time,close_reason,pnl_usdt FROM trades "
    "WHERE symbol IN ('MOVRUSDT','ALGOUSDT','BTCUSDT') ORDER BY id"
).fetchall():
    print(dict(r))
conn.close()

print("\n=== merter_dca_state.json ===")
with open(f"{ROOT}/signal_bot/merter_dca_state.json") as f:
    print(json.dumps(json.load(f), indent=2, ensure_ascii=False)[:3000])
