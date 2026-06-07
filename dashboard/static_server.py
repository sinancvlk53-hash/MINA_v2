#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dashboard static server — aiohttp, gzip + cache (port 3000)."""
from __future__ import annotations

import gzip
import mimetypes
import os
import sys

ROOT = os.environ.get("MINA_DATA_ROOT", "/root/MINA_v2")
DIST = os.path.join(ROOT, "dashboard", "dist")
PORT = int(os.environ.get("MINA_DASHBOARD_PORT", "3000"))
GZIP_MIN = 256

try:
    from aiohttp import web
except ImportError:
    print("ERROR: aiohttp required — pip install aiohttp", file=sys.stderr)
    sys.exit(1)

MIMETYPES = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".wasm": "application/wasm",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


def _cache_control(rel: str) -> str:
    norm = rel.replace("\\", "/").lstrip("/")
    if norm in ("", "index.html"):
        return "no-cache, must-revalidate"
    if norm.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    return "public, max-age=3600"


def _content_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in MIMETYPES:
        return MIMETYPES[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _compressible(ctype: str, size: int) -> bool:
    if size < GZIP_MIN:
        return False
    if ctype.startswith("text/"):
        return True
    return ctype in (
        "application/javascript",
        "application/json",
        "image/svg+xml",
        "application/wasm",
    )


async def handle_static(request: web.Request) -> web.Response:
    rel = request.match_info.get("path", "") or "index.html"
    rel = rel.lstrip("/")
    if ".." in rel.split("/"):
        raise web.HTTPForbidden()
    full = os.path.normpath(os.path.join(DIST, rel))
    if not full.startswith(os.path.normpath(DIST)):
        raise web.HTTPForbidden()
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    if not os.path.isfile(full):
        raise web.HTTPNotFound()

    with open(full, "rb") as f:
        raw = f.read()
    rel_path = os.path.relpath(full, DIST).replace("\\", "/")
    ctype = _content_type(full)
    body = raw
    headers = {
        "Cache-Control": _cache_control(rel_path),
        "Vary": "Accept-Encoding",
        "X-Content-Type-Options": "nosniff",
    }
    ae = request.headers.get("Accept-Encoding", "").lower()
    if _compressible(ctype, len(raw)) and "gzip" in ae:
        compressed = gzip.compress(raw, compresslevel=6)
        if len(compressed) < len(raw):
            body = compressed
            headers["Content-Encoding"] = "gzip"
    return web.Response(body=body, content_type=ctype, headers=headers)


def main() -> None:
    if not os.path.isdir(DIST):
        print(f"ERROR: dist not found: {DIST}", file=sys.stderr)
        sys.exit(1)
    app = web.Application()
    app.router.add_get("/", handle_static)
    app.router.add_get("/{path:.+}", handle_static)
    print(f"MINA dashboard aiohttp :{PORT}  root={DIST}")
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
