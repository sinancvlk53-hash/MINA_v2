#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Lokal ve sunucu .env dosyalarına Telegram satırlarını ekle."""
import os
import sys

import paramiko

LINES = """
# MINA Telegram listener (Telethon)
TELEGRAM_API_ID=38446219
TELEGRAM_API_HASH=72a15e6baf9f4f79893dd122258e8bea
TELEGRAM_MERTER_CHANNEL_ID=-1003769687656
TELEGRAM_HALUK_CHANNEL_ID=-1003062732797
TELEGRAM_SESSION_NAME=mina_listener
TELEGRAM_MERTER_SESSION=session
TELEGRAM_HALUK_SESSION=session_ht
""".strip()

KEYS = {
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_MERTER_CHANNEL_ID",
    "TELEGRAM_HALUK_CHANNEL_ID",
    "TELEGRAM_SESSION_NAME",
    "TELEGRAM_MERTER_SESSION",
    "TELEGRAM_HALUK_SESSION",
}


def append_env(path: str) -> None:
    existing = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    missing = [k for k in KEYS if f"{k}=" not in existing]
    if not missing:
        print(f"  {path}: tum anahtarlar mevcut")
        return
    with open(path, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n" + LINES + "\n")
    print(f"  {path}: eklendi ({', '.join(missing)})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    local = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    print("=== LOKAL ===")
    append_env(local)

    print("\n=== SUNUCU ===")
    host, user = "178.105.150.40", "root"
    pw = require_ssh_pass()
    remote = "/root/MINA_v2/.env"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username=user, password=pw, timeout=15)
    sftp = c.open_sftp()
    try:
        with sftp.open(remote, "r") as f:
            existing = f.read().decode("utf-8")
    except FileNotFoundError:
        existing = ""
    missing = [k for k in KEYS if f"{k}=" not in existing]
    if missing:
        with sftp.open(remote, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n" + LINES + "\n")
        print(f"  {remote}: eklendi ({', '.join(missing)})")
    else:
        print(f"  {remote}: tum anahtarlar mevcut")
    c.close()


if __name__ == "__main__":
    main()
