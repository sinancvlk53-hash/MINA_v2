#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dashboard oturum doğrulama — .env kimlik bilgileri + 24 saat HMAC token."""
import base64
import hashlib
import hmac
import json
import os
import time

SESSION_TTL = 24 * 3600


def _secret() -> str:
    return (
        os.environ.get("DASHBOARD_SESSION_SECRET")
        or os.environ.get("BINANCE_SECRET_KEY")
        or "mina-dashboard-default-secret"
    )


def get_credentials() -> tuple[str, str]:
    return (
        os.environ.get("DASHBOARD_USERNAME", "admin"),
        os.environ.get("DASHBOARD_PASSWORD", "admin"),
    )


def validate_login(username: str, password: str) -> bool:
    expected_user, expected_pass = get_credentials()
    return username == expected_user and password == expected_pass


def create_session_token(username: str) -> dict:
    exp = int(time.time()) + SESSION_TTL
    payload = {"sub": username, "exp": exp}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return {"token": f"{body}.{sig}", "expiresAt": exp * 1000}


def verify_session_token(token: str) -> tuple[bool, str | None]:
    if not token or "." not in token:
        return False, None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, None
    try:
        pad = (4 - len(body) % 4) % 4
        padded = body + ("=" * pad)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if int(payload.get("exp", 0)) < time.time():
            return False, None
        return True, payload.get("sub")
    except Exception:
        return False, None
