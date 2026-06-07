#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git geçmişinden SSH şifresini temizle — filter-repo veya filter-branch."""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET = "XnMUPFMNnNTf"
REPL = "REDACTED_SSH_PASS"


def main() -> None:
    os.chdir(ROOT)
    print("=== git log -S password ===")
    r = subprocess.run(
        ["git", "log", "--oneline", "--all", "-S", SECRET],
        capture_output=True, text=True,
    )
    print(r.stdout or r.stderr)
    if SECRET not in (r.stdout or ""):
        hits = subprocess.run(
            ["git", "grep", "-l", SECRET, "--all"],
            capture_output=True, text=True,
        )
        if hits.returncode != 0:
            print("git geçmişinde şifre bulunamadı (grep --all)")
            return

    repl_file = os.path.join(ROOT, ".git-secret-replacements.txt")
    with open(repl_file, "w", encoding="utf-8") as f:
        f.write(f"{SECRET}==>{REPL}\n")

    fr = subprocess.run(["git", "filter-repo", "--version"], capture_output=True, text=True)
    if fr.returncode == 0:
        print("=== git filter-repo --replace-text ===")
        subprocess.run(
            ["git", "filter-repo", "--force", "--replace-text", repl_file],
            check=False,
        )
    else:
        print("filter-repo yok — git filter-branch deneniyor...")
        env = os.environ.copy()
        env["FILTER_BRANCH_SQUELCH_WARNING"] = "1"
        cmd = (
            f'git filter-branch -f --tree-filter '
            f'"grep -rl \'{SECRET}\' . 2>/dev/null | while read f; do '
            f'sed -i \'s/{SECRET}/{REPL}/g\' \"$f\" 2>/dev/null || true; done" '
            f'--tag-name-filter cat -- --all'
        )
        subprocess.run(cmd, shell=True, env=env)

    os.remove(repl_file)
    print("=== doğrulama ===")
    v = subprocess.run(
        ["git", "log", "-p", "--all", "-S", SECRET],
        capture_output=True, text=True,
    )
    if SECRET in (v.stdout or ""):
        print("UYARI: geçmişte hâlâ şifre var — manuel filter-repo gerekli")
        sys.exit(1)
    print("temizlendi")


if __name__ == "__main__":
    main()
