#!/bin/bash
set -e
export PATH="$HOME/.deno/bin:$PATH"
if ! command -v deno >/dev/null 2>&1; then
  curl -fsSL https://deno.land/install.sh | sh
  export PATH="$HOME/.deno/bin:$PATH"
fi
deno --version
cd /root/MINA_v2/signal_bot/history
yt-dlp --cookies youtube_cookies.txt --js-runtimes deno \
  -x --audio-format mp3 \
  -o 'canli_yayin_20260608.mp3' \
  'https://youtube.com/live/kpnYLBT-H24'
