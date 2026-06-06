#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

TRANSCRIPT = "/root/MINA_v2/signal_bot/history/upbit_video_transcript.txt"

REMOTE_SCRIPT = r"""
set -e
echo "=== df -h ==="
df -h
echo
echo "=== TRANSCRIPT ==="
if [ -f """ + TRANSCRIPT + r""" ]; then
  ls -lh """ + TRANSCRIPT + r"""
  wc -c """ + TRANSCRIPT + r"""
else
  echo "YOK"
fi
echo
echo "=== UPBIT / VIDEO ARAMA ==="
find /root/MINA_v2 /tmp -maxdepth 5 -type f \( \
  -iname '*upbit*' -o -iname 'video' -o -iname 'video.*' -o -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.mov' -o -iname '*.webm' \
\) 2>/dev/null | while read f; do
  case "$f" in
    *upbit_video_transcript.txt) continue ;;
  esac
  ls -lh "$f"
done
echo
echo "=== TMP upbit_vid DIZINLERI ==="
find /tmp -maxdepth 2 -type d -name 'upbit_vid_*' 2>/dev/null | while read d; do
  du -sh "$d"
  ls -lah "$d"
done
echo
echo "=== SILME ==="
DELETED=0
find /tmp -maxdepth 2 -type d -name 'upbit_vid_*' 2>/dev/null | while read d; do
  rm -rf "$d" && echo "Silindi: $d" && DELETED=1
done
find /root/MINA_v2 /tmp -maxdepth 5 -type f \( -iname 'video' -o -iname 'video.*' -o -iname '*upbit*.mp4' -o -iname '*upbit*.mkv' \) 2>/dev/null | while read f; do
  rm -f "$f" && echo "Silindi: $f"
done
echo "Temizlik tamam"
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=require_ssh_pass(), timeout=20)
    _, o, e = c.exec_command(REMOTE_SCRIPT, timeout=120)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err)
    c.close()


if __name__ == "__main__":
    main()
