#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reset listed JSON state files and verify readiness."""
import json
import os
import subprocess
import sys

ROOT = "/root/MINA_v2"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)
os.environ.setdefault("MINA_DATA_ROOT", ROOT)

FILES = {
    "initial_entry_prices.json": ROOT,
    "defense_levels.json": ROOT,
    "tp_levels.json": ROOT,
    "max_prices.json": ROOT,
    "stop_levels.json": ROOT,
    "pending_orders.json": ROOT,
    "merter_dca_state.json": os.path.join(ROOT, "signal_bot"),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== JSON hafiza sifirlama ===")
    for name, base in FILES.items():
        path = os.path.join(base, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)
            f.write("\n")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ok = data == {}
        print(f"  {'OK' if ok else 'FAIL'} {path} -> {data}")

    print("\n=== DERR dokunulmadi ===")
    derr = os.path.join(ROOT, "mina_trading_journal.db")
    if os.path.isfile(derr):
        st = os.stat(derr)
        print(f"  mina_trading_journal.db mevcut, boyut={st.st_size} byte, degistirilmedi")
    else:
        print("  mina_trading_journal.db yok")

    print("\n=== Motor yeniden baslat (sync icin) ===")
    subprocess.run(["systemctl", "restart", "mina-engine.service"], check=False)
    subprocess.run(["systemctl", "restart", "mina-merter-dca.service"], check=False)
    subprocess.run(["sleep", "6"])

    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    from config import BinanceConfig, AccountManager
    from position_manager import PositionManager
    import mina_tracking as mt

    cfg = BinanceConfig()
    client = cfg.get_client()
    account = AccountManager(client)
    pm = PositionManager(client)

    balance = account.get_usdt_balance()
    slot = account.calculate_slot_size()
    entry_margin = account.calculate_entry_amount()
    positions = pm.get_all_positions()

    print("\n=== Binance testnet ===")
    print(f"  USDT bakiye     : {balance:.4f}")
    print(f"  Slot (kasa/10)  : {slot:.4f}")
    print(f"  Giris marjini   : {entry_margin:.4f}  (slot/5)")
    print(f"  Hacim (4x)      : {entry_margin * 4:.4f}")
    print(f"  Acik pozisyon   : {len(positions)}")

    print("\n=== JSON durumu (sifir sonrasi) ===")
    for name, base in FILES.items():
        path = os.path.join(base, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        preview = data if len(data) <= 2 else f"{{... {len(data)} keys ...}}"
        print(f"  {name}: {preview}")

    other = [
        "initial_margins.json",
        "mina_position_state.json",
        "defense_stop_orders.json",
        "position_sources.json",
    ]
    print("\n=== Diger state dosyalari (sifirlanmadi) ===")
    for name in other:
        data = mt.load_json(name)
        print(f"  {name}: {len(data)} kayit")

    issues = []
    if balance <= 0:
        issues.append("USDT bakiye 0 veya okunamadi")
    if slot <= 0:
        issues.append("Slot 0 — pozisyon acilamaz")
    if entry_margin <= 0:
        issues.append("Giris marjini 0")
    if positions:
        issues.append(f"Binance'te {len(positions)} acik pozisyon var (beklenen: 0)")

    for name, base in FILES.items():
        path = os.path.join(base, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data:
            issues.append(f"{name} hala bos degil: {list(data.keys())[:3]}")

    svc = subprocess.run(
        ["systemctl", "is-active", "mina-engine.service", "mina-merter-dca.service", "mina-listener.service"],
        capture_output=True,
        text=True,
    )
    svc_lines = svc.stdout.strip().split("\n")
    svc_names = ["mina-engine", "mina-merter-dca", "mina-listener"]
    for n, s in zip(svc_names, svc_lines):
        if s != "active":
            issues.append(f"{n} servisi active degil: {s}")

    print("\n=== Hazirlik ozeti ===")
    ready = balance > 0 and slot > 0 and not positions and not issues
    if ready:
        print("  HAZIR — yeni pozisyon acmaya uygun")
        print(f"  Ornek: 1 slot={slot:.2f} USDT, giris marjini={entry_margin:.2f}, 4x hacim={entry_margin*4:.2f}")
    else:
        print("  UYARI — asagidaki maddeler:")
        for i in issues:
            print(f"    - {i}")

    print("\n=== mina_bot.log son 5 satir ===")
    log = os.path.join(ROOT, "mina_bot.log")
    if os.path.isfile(log):
        with open(log, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-5:]:
                print(line.rstrip())


if __name__ == "__main__":
    main()
