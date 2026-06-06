# -*- coding: utf-8 -*-
"""SSH bağlantı yardımcıları — MINA_SSH_PASS zorunlu, hardcoded şifre yok."""

from __future__ import annotations

import os
import sys

SSH_HOST = os.environ.get("MINA_SSH_HOST", "178.105.150.40")
SSH_USER = os.environ.get("MINA_SSH_USER", "root")


def require_ssh_pass() -> str:
    """MINA_SSH_PASS yoksa script'i durdur."""
    pwd = os.environ.get("MINA_SSH_PASS")
    if not pwd or not str(pwd).strip():
        print(
            "HATA: MINA_SSH_PASS ortam değişkeni zorunlu. "
            "Örnek: set MINA_SSH_PASS=... (Windows) veya export MINA_SSH_PASS=... (Linux)",
            file=sys.stderr,
        )
        sys.exit(1)
    return str(pwd).strip()
