# -*- coding: utf-8 -*-
"""
raw_signal_queue.json izleyici — yeni Merter kayıtlarında pipeline + DERR.

Kullanım:
  python signal_bot/queue_watcher.py          # sürekli izle (yeni sinyal bekle)
  python signal_bot/queue_watcher.py --once   # tek tarama + özet
  python signal_bot/queue_watcher.py --baseline  # mevcut kayıtları atla, sadece yeniler
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from signal_bot.signal_parser import RAW_QUEUE_FILE, load_queue
from signal_bot.signal_pipeline import (
    entry_fingerprint,
    print_queue_fragments,
    process_merter_entry,
    queue_snapshot,
)

STATE_FILE = os.path.join(os.path.dirname(__file__), "queue_watcher_state.json")
POLL_SEC = 2.0


def _load_state() -> dict:
    if not os.path.isfile(STATE_FILE):
        return {"processed": []}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"processed": []}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _processed_set(state: dict) -> set:
    return set(state.get("processed") or [])


def baseline_current(queue: dict, state: dict) -> int:
    """Mevcut tüm entry fingerprint'lerini işlenmiş say (geçmişi atla)."""
    done = _processed_set(state)
    n = 0
    for ent in queue.get("entries") or []:
        fp = entry_fingerprint(ent)
        if fp not in done:
            done.add(fp)
            n += 1
    state["processed"] = sorted(done)
    state["baselined_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_state(state)
    return n


def scan_new_merter(*, print_fragments: bool = True) -> int:
    queue = load_queue()
    state = _load_state()
    done = _processed_set(state)
    count = 0

    if print_fragments:
        print_queue_fragments()

    for ent in queue.get("entries") or []:
        if ent.get("source") != "merter":
            continue
        fp = entry_fingerprint(ent)
        if fp in done:
            continue
        if ent.get("status") != "approved":
            done.add(fp)
            continue

        process_merter_entry(ent, queue=queue)
        done.add(fp)
        count += 1

    state["processed"] = sorted(done)
    state["last_scan"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["last_queue_updated"] = queue.get("updated_at")
    _save_state(state)
    return count


def watch_loop() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("MINA queue_watcher — raw_signal_queue.json izleniyor", flush=True)
    print(f"  dosya: {RAW_QUEUE_FILE}", flush=True)
    print(f"  state: {STATE_FILE}", flush=True)
    print("  Yeni Merter sinyali gelince pipeline + DERR yazılır.", flush=True)
    print("  Durdurmak: Ctrl+C\n", flush=True)

    state = _load_state()
    if not state.get("baselined_at"):
        queue = load_queue()
        n = baseline_current(queue, state)
        print(f"  [baseline] {n} mevcut kayıt işlenmiş sayıldı (geçmiş atlandı).\n", flush=True)

    last_updated = None
    while True:
        try:
            queue = load_queue()
            upd = queue.get("updated_at")
            if upd != last_updated:
                snap = queue_snapshot(queue)
                print(
                    f"[kuyruk] updated={upd} entries={snap['entries_total']} "
                    f"merter={snap['merter_count']} TOTAL={snap['total_direction']}",
                    flush=True,
                )
                last_updated = upd
            n = scan_new_merter(print_fragments=False)
            if n:
                print(f"  → {n} yeni Merter işlendi.\n", flush=True)
        except KeyboardInterrupt:
            print("\nİzleme durdu. Mimar ile gerçek sinyalde devam.", flush=True)
            break
        except Exception as e:
            print(f"[watcher hata] {e}", flush=True)
        time.sleep(POLL_SEC)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Tek tarama")
    parser.add_argument("--baseline", action="store_true", help="Mevcut kayıtları atla")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.baseline:
        state = _load_state()
        n = baseline_current(load_queue(), state)
        print(f"Baseline: {n} fingerprint kaydedildi.")
        return

    if args.once:
        n = scan_new_merter()
        print(f"\nTek tarama: {n} yeni Merter pipeline çalıştı.")
        return

    watch_loop()


if __name__ == "__main__":
    main()
