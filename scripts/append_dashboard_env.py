#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lokal ve sunucu .env dosyalarına dashboard kimlik bilgilerini ekle."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER

import paramiko

LINES = """
# MINA Dashboard auth
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=admin
""".strip()

KEYS = {"DASHBOARD_USERNAME", "DASHBOARD_PASSWORD"}


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
    local = os.path.join(_ROOT, ".env")
    print("=== LOKAL ===")
    append_env(local)

    print("\n=== SUNUCU ===")
    pw = require_ssh_pass()
    remote = "/root/MINA_v2/.env"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=pw, timeout=15)
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
