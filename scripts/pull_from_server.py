#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Sunucudan /root/MINA_v2 → lokal repo SFTP sync (venv/node_modules hariç)."""
from __future__ import annotations

import os
import stat
import sys

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".mina_health_cache",
    "agent-transcripts",
}
SKIP_FILES = {
    ".env",
}


def should_skip(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if any(p in SKIP_DIRS for p in parts):
        return True
    if parts[-1] in SKIP_FILES:
        return True
    return False


def sync_dir(sftp, remote_dir: str, local_dir: str, stats: dict) -> None:
    for entry in sftp.listdir_attr(remote_dir):
        name = entry.filename
        if name in (".", ".."):
            continue
        remote_path = f"{remote_dir}/{name}"
        rel = os.path.relpath(remote_path, REMOTE).replace("\\", "/")
        if should_skip(rel):
            continue
        local_path = os.path.join(local_dir, rel.replace("/", os.sep))
        if stat.S_ISDIR(entry.st_mode):
            os.makedirs(local_path, exist_ok=True)
            sync_dir(sftp, remote_path, local_dir, stats)
        else:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            sftp.get(remote_path, local_path)
            stats["files"] += 1
            if stats["files"] % 50 == 0:
                print(f"  ... {stats['files']} files")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Sync {REMOTE} → {LOCAL}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()
    stats = {"files": 0}
    sync_dir(sftp, REMOTE, LOCAL, stats)
    sftp.close()
    c.close()
    print(f"Done: {stats['files']} files synced")


if __name__ == "__main__":
    main()
