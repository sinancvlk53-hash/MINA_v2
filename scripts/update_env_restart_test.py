#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update .env API keys, restart services, test Binance."""
import os
import re
import subprocess
import sys

ENV_PATH = "/root/MINA_v2/.env"
NEW_KEY = "REDACTED"
NEW_SECRET = "REDACTED"

KEY_ALIASES = [
    "BINANCE_TESTNET_API_KEY",
    "BINANCE_API_KEY",
]
SECRET_ALIASES = [
    "BINANCE_TESTNET_API_SECRET",
    "BINANCE_SECRET_KEY",
    "BINANCE_API_SECRET",
]

SERVICES = [
    "mina-engine.service",
    "mina-merter-dca.service",
    "mina-listener.service",
    "mina-queue-watcher.service",
    "mina-dashboard-ws.service",
    "mina-dashboard-vite.service",
]


def load_env(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def set_or_add(lines, name, value):
    pat = re.compile(rf"^{re.escape(name)}=")
    out = []
    found = False
    for line in lines:
        if pat.match(line):
            out.append(f"{name}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{name}={value}")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lines = load_env(ENV_PATH)

    for name in KEY_ALIASES:
        lines = set_or_add(lines, name, NEW_KEY)
    for name in SECRET_ALIASES:
        lines = set_or_add(lines, name, NEW_SECRET)
    lines = set_or_add(lines, "BINANCE_TESTNET", "true")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    os.chmod(ENV_PATH, 0o600)
    print(f"OK .env guncellendi: {ENV_PATH}")
    print("Guncellenen anahtarlar:", ", ".join(KEY_ALIASES + SECRET_ALIASES + ["BINANCE_TESTNET"]))

    # listener clean restart
    subprocess.run(
        "systemctl stop mina-listener.service 2>/dev/null; "
        "pkill -9 -f '/root/MINA_v2/venv/bin/python signal_bot/listener.py' 2>/dev/null; "
        "rm -f /root/MINA_v2/signal_bot/listener.lock; "
        "sleep 2",
        shell=True,
    )
    for svc in SERVICES:
        print(f">>> restart {svc}")
        subprocess.run(["systemctl", "restart", svc], check=False)
    subprocess.run(["sleep", "5"])

    print("\n=== Binance testnet baglanti testi ===")
    sys.path.insert(0, "/root/MINA_v2")
    os.chdir("/root/MINA_v2")
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
    try:
        from backend.config import BinanceConfig, AccountManager
        cfg = BinanceConfig()
        client = cfg.get_client()
        bal = client.futures_account_balance()
        usdt = next((float(x["balance"]) for x in bal if x["asset"] == "USDT"), 0.0)
        pos = client.futures_position_information()
        open_pos = [p for p in pos if float(p.get("positionAmt") or 0) != 0]
        print(f"OK futures_account_balance USDT={usdt:.4f}")
        print(f"OK futures_position_information acik_pozisyon={len(open_pos)}")
        print("OK -1109 yok, baglanti calisiyor")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        sys.exit(1)

    print("\n=== Servis durumu ===")
    subprocess.run(
        "systemctl is-active " + " ".join(SERVICES),
        shell=True,
    )

    print("\n=== mina_bot.log son 10 satir ===")
    log = "/root/MINA_v2/mina_bot.log"
    if os.path.isfile(log):
        with open(log, encoding="utf-8", errors="replace") as f:
            tail = f.readlines()[-10:]
        for line in tail:
            print(line.rstrip())
    else:
        print("(log yok)")


if __name__ == "__main__":
    main()
