#!/bin/bash
echo "=== son 15 BTCUSDT satiri ==="
grep BTCUSDT /root/MINA_v2/mina_bot.log | tail -15
echo
echo "=== tail -f (20 saniye, grep BTCUSDT) ==="
timeout 20 tail -f /root/MINA_v2/mina_bot.log 2>/dev/null | grep --line-buffered BTCUSDT || true
