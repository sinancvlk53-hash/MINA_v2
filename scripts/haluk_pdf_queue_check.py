#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Haluk PDF 14:27 sinyalleri — kuyruk durumu analizi."""
import json
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
ROOT = "/root/MINA_v2"

REMOTE = r'''#!/usr/bin/env python3
import json, os, sqlite3
from datetime import datetime

ROOT = "/root/MINA_v2"
QUEUE = ROOT + "/signal_bot/raw_signal_queue.json"
STATE = ROOT + "/signal_bot/queue_watcher_state.json"
PDF = "tg_20260604_142710_11448.pdf"

def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}

print("=" * 72)
print("1) raw_signal_queue.json — genel özet")
print("=" * 72)
q = load(QUEUE)
entries = q.get("entries") or []
print(f"updated_at: {q.get('updated_at')}")
print(f"toplam entries: {len(entries)}")

by_status = {}
by_source = {}
by_state = {}
for e in entries:
    st = e.get("status") or "?"
    src = e.get("source") or "?"
    qs = e.get("queue_state") or "active"
    by_status[st] = by_status.get(st, 0) + 1
    by_source[src] = by_source.get(src, 0) + 1
    by_state[qs] = by_state.get(qs, 0) + 1
print("status:", by_status)
print("source:", by_source)
print("queue_state:", by_state)

print("\n" + "=" * 72)
print("2) Bugün 2026-06-04 veya PDF/Haluk kaynaklı sinyaller")
print("=" * 72)

def match_entry(e):
    ts = str(e.get("timestamp") or e.get("created_at") or "")
    raw = str(e.get("raw_snippet") or e.get("raw_text") or "")
    src = str(e.get("source") or "")
    if "2026-06-04" in ts or "2026-06-04" in raw:
        return True
    if src.lower() in ("haluk", "haluk_pdf", "pdf"):
        return True
    if "14:27" in ts or PDF in raw:
        return True
    return False

today = [e for e in entries if match_entry(e)]
print(f"eşleşen kayıt: {len(today)}")

# PDF sonrası ~14:27 UTC entries — also grep haluk in snippet
haluk_pdf = []
for e in entries:
    raw = json.dumps(e, ensure_ascii=False).lower()
    if "haluk" in raw or e.get("source") in ("haluk", "haluk_pdf", "pdf"):
        haluk_pdf.append(e)
    elif e.get("source") == "merter" and "2026-06-04" in str(e.get("timestamp","")):
        pass

# Show all entries from source haluk or with pdf path
pdf_entries = []
for e in entries:
    src = (e.get("source") or "").lower()
    raw = str(e.get("raw_snippet") or e.get("raw_text") or "")
    if src in ("haluk", "haluk_pdf", "pdf") or PDF in raw or "142710" in raw:
        pdf_entries.append(e)

if not pdf_entries:
    # fallback: last 20 entries
    pdf_entries = entries[-20:]

print(f"\nHaluk/PDF ile ilişkili: {len(pdf_entries)} kayıt\n")
cols = ["symbol", "direction", "source", "status", "queue_state", "timestamp", "k2_label", "reject_reason"]
print("  ".join(f"{c:>14}" for c in cols))
print("-" * 100)
for e in pdf_entries:
    print("  ".join(f"{str(e.get(c) or e.get('direction') or '—'):>14}" for c in cols if c != 'direction'))
    if e.get("direction"):
        pass
    row = [
        e.get("symbol", "—"),
        e.get("direction", "—"),
        e.get("source", "—"),
        e.get("status", "—"),
        e.get("queue_state", "—"),
        (e.get("timestamp") or "—")[:19],
        e.get("k2_label") or e.get("label") or "—",
        e.get("reject_reason") or "—",
    ]
    print("  ".join(f"{str(x):>14}" for x in row))
    snip = (e.get("raw_snippet") or "")[:80]
    if snip:
        print(f"    snippet: {snip}")

print("\n" + "=" * 72)
print("3) queue_watcher_state.json")
print("=" * 72)
print(json.dumps(load(STATE), indent=2, ensure_ascii=False))

print("\n" + "=" * 72)
print("4) signal_decisions — bugün Haluk/PDF (2026-06-04)")
print("=" * 72)
db = ROOT + "/mina_trading_journal.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
rows = con.execute("""
SELECT id, merter_symbol, merter_direction, k2_label, k3_action, k2_reason, created_at, scenario_label
FROM signal_decisions WHERE date(created_at)='2026-06-04'
ORDER BY created_at
""").fetchall()
for r in rows:
    print(dict(r))
con.close()

print("\n" + "=" * 72)
print("5) Servis durumları + son log")
print("=" * 72)
import subprocess
for svc in ["mina-queue-watcher.service", "mina-engine.service", "mina-listener.service"]:
    r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
    print(f"{svc}: {r.stdout.strip() or r.stderr.strip()}")

r = subprocess.run(
    ["grep", "-i", "haluk\\|pdf\\|slot_bridge\\|SLOT_BRIDGE", ROOT + "/mina_bot.log"],
    capture_output=True, text=True
)
lines = [l for l in r.stdout.splitlines() if "2026-06-04" in l][-15:]
print("\nmina_bot.log (son 15 ilgili):")
print("\n".join(lines) if lines else "(yok)")

r2 = subprocess.run(
    ["grep", "-i", "142710\\|haluk pdf", ROOT + "/signal_bot/signals_log.txt"],
    capture_output=True, text=True
)
print("\nsignals_log PDF satırları:")
print(r2.stdout.strip() or "(yok)")

# Parse haluk pdf parser output if separate queue
htq = ROOT + "/signal_bot/ht_signals_queue.json"
if os.path.isfile(htq):
    print("\n" + "=" * 72)
    print("6) ht_signals_queue.json")
    print("=" * 72)
    ht = load(htq)
    print(f"entries: {len(ht.get('entries') or [])}")
    for e in (ht.get("entries") or [])[-15:]:
        print(f"  {e.get('symbol')} {e.get('direction')} status={e.get('status')} ts={e.get('timestamp','')[:19]}")
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)
    path = f"{ROOT}/scripts/_haluk_pdf_queue_check.py"
    sftp = c.open_sftp()
    with sftp.open(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, stdout, stderr = c.exec_command(f"{ROOT}/venv/bin/python {path}", timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    e = stderr.read().decode("utf-8", errors="replace")
    if e.strip():
        print("STDERR:", e)
    c.close()

if __name__ == "__main__":
    main()
