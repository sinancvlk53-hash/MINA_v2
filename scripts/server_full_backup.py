#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sunucuda /root/MINA_v2 tam tar.gz yedeği al."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")

BACKUP_CMD = r"""
set -e
mkdir -p /root/backups
STAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="/root/backups/MINA_v2_${STAMP}.tar.gz"
echo ">>> Creating $ARCHIVE"
tar -czf "$ARCHIVE" -C /root MINA_v2
ls -lh "$ARCHIVE"
echo ">>> Backup path: $ARCHIVE"
echo ">>> Disk usage /root/backups:"
du -sh /root/backups
ls -lt /root/backups | head -5
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    _, out, err = c.exec_command(BACKUP_CMD, timeout=600)
    o = out.read().decode()
    e = err.read().decode()
    if o:
        print(o)
    if e:
        print("ERR:", e)
    code = out.channel.recv_exit_status()
    c.close()
    if code != 0:
        sys.exit(code)
    print(">>> Sunucu yedeği tamamlandı.")


if __name__ == "__main__":
    main()
