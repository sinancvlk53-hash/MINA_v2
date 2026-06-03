#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sunucuda .env ve .session kontrolü."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)

    commands = [
        f"ls -la {REMOTE}/ | grep -E '.env|.session' || true",
        f"ls -la {REMOTE}/signal_bot/ | grep -E '.env|.session' || true",
        f"find {REMOTE} -maxdepth 3 \\( -name '*.session' -o -name '*.session-journal' \\) 2>/dev/null",
        f"test -f {REMOTE}/.env && echo '.env: VAR' || echo '.env: YOK'",
        f"grep -E '^TELEGRAM_API_ID=|^TELEGRAM_API_HASH=' {REMOTE}/.env 2>/dev/null | sed 's/=.*/=<MASKED>/' || echo 'TELEGRAM_API_*: YOK'",
        f"grep -v '^#' {REMOTE}/.env 2>/dev/null | grep '=' | cut -d= -f1 | sort",
    ]

    print("=== SUNUCU", REMOTE, "===\n")
    for cmd in commands:
        print(">>>", cmd)
        _, out, err = c.exec_command(cmd, timeout=25)
        o = out.read().decode("utf-8", errors="replace").strip()
        e = err.read().decode("utf-8", errors="replace").strip()
        print(o if o else "(bos)")
        if e:
            print("stderr:", e)
        print()

    c.close()


if __name__ == "__main__":
    main()
