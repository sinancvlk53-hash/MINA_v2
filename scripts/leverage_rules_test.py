#!/usr/bin/env python3
"""Kaldıraç kuralları canlı test — JSON manipülasyonu + log/state doğrulama."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

ROOT = os.environ.get("MINA_ROOT", "/root/MINA_v2")
LOG_FILE = os.path.join(ROOT, "mina_bot.log")
BACKUP_DIR = os.path.join(ROOT, "scripts", "_leverage_test_backup")

FILES = {
    "initial_entry": os.path.join(ROOT, "initial_entry_prices.json"),
    "defense": os.path.join(ROOT, "defense_levels.json"),
    "tp": os.path.join(ROOT, "tp_levels.json"),
    "max_prices": os.path.join(ROOT, "max_prices.json"),
}


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def backup_all() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for name, path in FILES.items():
        if os.path.isfile(path):
            shutil.copy2(path, os.path.join(BACKUP_DIR, f"{name}.json"))


def restore_all() -> None:
    for name, path in FILES.items():
        bp = os.path.join(BACKUP_DIR, f"{name}.json")
        if os.path.isfile(bp):
            shutil.copy2(bp, path)


def restore_file(name: str) -> None:
    bp = os.path.join(BACKUP_DIR, f"{name}.json")
    if os.path.isfile(bp):
        shutil.copy2(bp, FILES[name])


def log_line_count() -> int:
    if not os.path.isfile(LOG_FILE):
        return 0
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def log_since(line_start: int, symbol: str) -> List[str]:
    if not os.path.isfile(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return [ln.rstrip() for ln in lines[line_start:] if symbol.replace("USDT", "") in ln or symbol in ln]


def get_marks(symbols: List[str]) -> Dict[str, float]:
    sys.path.insert(0, ROOT)
    from backend.config import BinanceConfig

    client = BinanceConfig().get_client()
    out = {}
    for sym in symbols:
        r = client.futures_mark_price(symbol=sym)
        out[sym] = float(r["markPrice"])
    return out


def pos_keys() -> List[str]:
    initial = load_json(FILES["initial_entry"])
    return list(initial.keys())


def symbol_from_key(key: str) -> str:
    return key.replace("_LONG", "").replace("_SHORT", "")


def wait_cycles(seconds: int = 60) -> None:
    print(f"  ... {seconds}s bekleniyor (motor interval=30s)")
    time.sleep(seconds)


def run_test(
    key: str,
    test_name: str,
    mutate_fn,
    expect_log: List[str],
    check_fn,
) -> Dict[str, Any]:
    sym = symbol_from_key(key)
    line_start = log_line_count()
    before = {n: load_json(p) for n, p in FILES.items()}

    print(f"\n{'='*60}")
    print(f"TEST: {test_name} | {key} | {datetime.now().isoformat(timespec='seconds')}")
    mutate_fn(key, sym)
    print(f"  MUTATE sonrası:")
    for n in ("initial_entry", "defense", "tp", "max_prices"):
        print(f"    {n}: {json.dumps(before[n].get(key) if n != 'initial_entry' else load_json(FILES[n]).get(key))}")

    wait_cycles(60)

    after_defense = load_json(FILES["defense"]).get(key, 0)
    after_tp = load_json(FILES["tp"]).get(key, 0)
    logs = log_since(line_start, sym)
    check = check_fn(before, after_defense, after_tp, logs)

    print(f"  LOG ({sym}):")
    for ln in logs[-15:]:
        print(f"    {ln}")
    if not logs:
        print("    (yeni log yok)")
    print(f"  defense_levels[{key}] = {after_defense}")
    print(f"  tp_levels[{key}] = {after_tp}")

    restore_all()
    print(f"  GERİ YÜKLENDİ")

    matched = [p for p in expect_log if any(p.lower() in ln.lower() for ln in logs)]
    result = {
        "test": test_name,
        "key": key,
        "symbol": sym,
        "defense_after": after_defense,
        "tp_after": after_tp,
        "logs": logs,
        "matched_patterns": matched,
        "status": check,
    }
    print(f"  SONUÇ: {check}")
    return result


def main() -> None:
    os.chdir(ROOT)
    backup_all()
    marks = get_marks(["ZECUSDT", "MYXUSDT", "FHEUSDT"])
    keys = pos_keys()
    results: List[Dict[str, Any]] = []

    print("=== BAŞLANGIÇ DURUMU ===")
    for n, p in FILES.items():
        print(f"\n--- {os.path.basename(p)} ---")
        print(json.dumps(load_json(p), indent=2))
    print(f"\n--- mark fiyatları ---")
    for k, v in marks.items():
        print(f"  {k}: {v}")
    print(f"\n--- log tail ---")
    os.system(f"tail -10 {LOG_FILE}")

    for key in keys:
        sym = symbol_from_key(key)
        mark = marks[sym]

        # TP1
        orig_max = load_json(FILES["max_prices"]).get(key)

        def tp1_mutate(k, s):
            mp = load_json(FILES["max_prices"])
            mp[k] = round(mark / 0.97, 8)
            save_json(FILES["max_prices"], mp)

        def tp1_check(before, def_after, tp_after, logs):
            if tp_after >= 1 or any("take_profit" in ln and "level': 1" in ln or "level\": 1" in ln or "'level': 1" in ln for ln in logs):
                return "✅ Çalışıyor"
            if any("take_profit" in ln for ln in logs):
                return "⚠️ Kısmen"
            return "❌ Çalışmıyor"

        results.append(run_test(
            key, "TP1", tp1_mutate,
            ["take_profit", "TP1", "level': 1"],
            tp1_check,
        ))

        # D1
        orig_entry = load_json(FILES["initial_entry"]).get(key)

        def d1_mutate(k, s):
            ie = load_json(FILES["initial_entry"])
            ie[k] = round(mark / 0.94, 8)
            save_json(FILES["initial_entry"], ie)

        def d1_check(before, def_after, tp_after, logs):
            if def_after >= 1 or any("defense" in ln and "D1" in ln for ln in logs):
                return "✅ Çalışıyor"
            if any("defense" in ln.lower() or "d1" in ln.lower() for ln in logs):
                return "⚠️ Kısmen"
            return "❌ Çalışmıyor"

        results.append(run_test(
            key, "D1", d1_mutate,
            ["defense", "D1"],
            d1_check,
        ))

        # D2
        def d2_mutate(k, s):
            ie = load_json(FILES["initial_entry"])
            ie[k] = round(mark / 0.87, 8)
            save_json(FILES["initial_entry"], ie)

        def d2_check(before, def_after, tp_after, logs):
            ok_def = def_after >= 2
            ok_log = any(
                ("D2" in ln or "defense_level': 2" in ln or "defense_level\": 2" in ln or "breakeven" in ln.lower() or "tp_disabled" in ln.lower())
                for ln in logs
            )
            if ok_def and ok_log:
                return "✅ Çalışıyor"
            if ok_def or ok_log:
                return "⚠️ Kısmen"
            return "❌ Çalışmıyor"

        results.append(run_test(
            key, "D2", d2_mutate,
            ["D2", "breakeven", "defense"],
            d2_check,
        ))

    restore_all()
    print("\n" + "=" * 60)
    print("=== ÖZET RAPOR ===")
    for r in results:
        print(f"{r['symbol']:10} {r['test']:5} → {r['status']}  (def={r['defense_after']} tp={r['tp_after']})")


if __name__ == "__main__":
    main()
