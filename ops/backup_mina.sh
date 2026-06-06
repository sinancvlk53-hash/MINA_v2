#!/bin/bash
# MINA v2 gece yedeği — cron: 0 2 * * *
set -euo pipefail
ROOT="/root/MINA_v2"
DEST="/root/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="${DEST}/MINA_v2_${STAMP}.tar.gz"

mkdir -p "$DEST"
tar -czf "$ARCHIVE" \
  --exclude='venv' \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='__pycache__' \
  -C /root MINA_v2

find "$DEST" -name 'MINA_v2_*.tar.gz' -mtime +7 -delete
echo "$(date -Iseconds) backup ok: $ARCHIVE"
