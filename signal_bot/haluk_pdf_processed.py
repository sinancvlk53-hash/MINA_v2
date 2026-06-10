# -*- coding: utf-8 -*-
"""Haluk PDF işlendi mi — listener / pdf_listener çift pipeline önleme."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SIGNAL_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_PDFS_FILE = os.path.join(SIGNAL_BOT_DIR, "processed_pdfs.json")
_MAX_ENTRIES = 200

_lock = threading.Lock()


def _ts_key_from_name(basename: str) -> Optional[str]:
    m = re.search(r"(\d{8}_\d{6})", basename)
    return m.group(1) if m else None


def _sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load_data() -> Dict[str, Any]:
    if not os.path.isfile(PROCESSED_PDFS_FILE):
        return {"entries": []}
    try:
        with open(PROCESSED_PDFS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if "entries" not in data:
            data["entries"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"entries": []}


def _save_data(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PROCESSED_PDFS_FILE), exist_ok=True)
    entries: List[Dict[str, Any]] = data.get("entries") or []
    if len(entries) > _MAX_ENTRIES:
        data["entries"] = entries[-_MAX_ENTRIES:]
    with open(PROCESSED_PDFS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_pdf_processed(pdf_path: str) -> bool:
    """Dosya adı, içerik hash veya zaman damgası anahtarı ile kontrol."""
    if not pdf_path:
        return False
    name = os.path.basename(pdf_path)
    sha = _sha256_file(pdf_path) if os.path.isfile(pdf_path) else None
    ts_key = _ts_key_from_name(name)

    with _lock:
        for entry in _load_data().get("entries") or []:
            if entry.get("name") == name:
                return True
            if sha and entry.get("sha256") == sha:
                return True
            if ts_key and entry.get("ts_key") == ts_key:
                return True
    return False


def mark_pdf_processed(pdf_path: str) -> None:
    """İşlenen PDF'i kaydet (listener veya approval_bot sonrası)."""
    if not pdf_path or not os.path.isfile(pdf_path):
        return
    name = os.path.basename(pdf_path)
    entry = {
        "name": name,
        "sha256": _sha256_file(pdf_path),
        "ts_key": _ts_key_from_name(name),
        "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with _lock:
        data = _load_data()
        entries: List[Dict[str, Any]] = data.setdefault("entries", [])
        for existing in entries:
            if existing.get("name") == name:
                return
            if entry.get("sha256") and existing.get("sha256") == entry.get("sha256"):
                return
            if entry.get("ts_key") and existing.get("ts_key") == entry.get("ts_key"):
                return
        entries.append(entry)
        _save_data(data)
