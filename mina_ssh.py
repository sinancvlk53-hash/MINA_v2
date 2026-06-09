# -*- coding: utf-8 -*-
"""SSH bağlantı yardımcıları — önce SSH key, opsiyonel MINA_SSH_PASS."""

from __future__ import annotations

import os
import sys
from typing import Optional

SSH_HOST = os.environ.get("MINA_SSH_HOST", "178.105.150.40")
SSH_USER = os.environ.get("MINA_SSH_USER", "root")


def get_ssh_pass() -> Optional[str]:
    """MINA_SSH_PASS varsa döndür, yoksa None (SSH key kullanılır)."""
    pwd = os.environ.get("MINA_SSH_PASS")
    if pwd and str(pwd).strip():
        return str(pwd).strip()
    return None


def require_ssh_pass() -> str:
    """MINA_SSH_PASS yoksa script'i durdur (eski script uyumluluğu)."""
    pwd = get_ssh_pass()
    if not pwd:
        print(
            "HATA: MINA_SSH_PASS ortam değişkeni zorunlu. "
            "Örnek: set MINA_SSH_PASS=... (Windows) veya export MINA_SSH_PASS=... (Linux)",
            file=sys.stderr,
        )
        sys.exit(1)
    return pwd


def connect_paramiko(client, host: Optional[str] = None, user: Optional[str] = None, timeout: int = 30) -> None:
    """Paramiko SSHClient — önce SSH key/agent, opsiyonel şifre."""
    host = host or SSH_HOST
    user = user or SSH_USER
    pwd = get_ssh_pass()
    kwargs = {
        "hostname": host,
        "username": user,
        "timeout": timeout,
        "look_for_keys": True,
        "allow_agent": True,
    }
    if pwd:
        kwargs["password"] = pwd
    client.connect(**kwargs)
