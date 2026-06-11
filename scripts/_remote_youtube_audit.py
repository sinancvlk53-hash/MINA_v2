#!/usr/bin/env python3
import sys
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko

CMD = r"""bash << 'BASH_EOF'
set +e

echo "========== 1. haluk_yayin_analiz.py =========="
cat /root/MINA_v2/signal_bot/haluk_yayin_analiz.py

echo ""
echo "========== 2. haluk_video_transcriber.py =========="
cat /root/MINA_v2/signal_bot/haluk_video_transcriber.py

echo ""
echo "========== 3. listener.py =========="
cat /root/MINA_v2/signal_bot/listener.py

echo ""
echo "========== 4. whisper/model grep =========="
grep -rn "whisper\|model\|base\|small\|medium\|large" /root/MINA_v2/signal_bot/ --include="*.py" 2>/dev/null | grep -v venv | head -30

echo ""
echo "========== 5. cookie grep + ls =========="
grep -rn "cookie\|cookies\|youtube_cookies" /root/MINA_v2/signal_bot/ --include="*.py" 2>/dev/null | head -20
ls -la /root/MINA_v2/signal_bot/history/youtube_cookies.txt 2>/dev/null || echo "COOKIE DOSYASI YOK"

echo ""
echo "========== 6. yayin_analiz_state.json =========="
cat /root/MINA_v2/signal_bot/history/yayin_analiz_state.json 2>/dev/null | python3 -m json.tool | head -40 || echo "STATE DOSYASI YOK"

echo ""
echo "========== 7. sqlite schema =========="
cd /root/MINA_v2 && python3 << 'PYEOF'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
cursor = conn.cursor()
tables = [t[0] for t in cursor.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()]
print('=== MEVCUT TABLOLAR VE ŞEMALARI ===')
for table in tables:
    print(f'\n[Tablo: {table}]')
    columns = cursor.execute(f'PRAGMA table_info({table})').fetchall()
    for col in columns:
        print(f'  - ID:{col[0]} İsim:{col[1]} Tip:{col[2]}')
conn.close()
PYEOF

BASH_EOF
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connect_paramiko(c)
_, o, e = c.exec_command(CMD, timeout=300)
out = o.read().decode("utf-8", errors="replace")
err = e.read().decode("utf-8", errors="replace")
out_path = os.path.join(_ROOT, "scripts", "_youtube_audit_output.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(out)
    if err.strip():
        f.write("\n=== STDERR ===\n" + err)
sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
if err.strip():
    sys.stdout.buffer.write(b"\n=== STDERR ===\n")
    sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
c.close()
print(f"\n[Saved: {out_path}]", flush=True)
