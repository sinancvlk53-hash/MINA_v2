#!/usr/bin/env python3
"""Sunucu 16-18: API çağrısı yok (rate limit)."""
import os
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
out_path = os.path.join(os.path.dirname(__file__), "..", "health_11_18_supplement.txt")

SCRIPT = r"""
echo '================================================================================'
echo '16) Haluk PDF son durum'
echo '================================================================================'
ls -la /root/MINA_v2/signal_bot/macro_levels.json 2>&1
echo '--- macro_levels.json head ---'
head -c 2500 /root/MINA_v2/signal_bot/macro_levels.json 2>&1
echo
echo '--- PDF dosyalari (son 10) ---'
find /root/MINA_v2 -name '*.pdf' -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %p\n' 2>/dev/null | sort -r | head -10
echo '--- signals_log PDF/onay son 15 ---'
grep -iE 'pdf|macro_levels|onay|approved' /root/MINA_v2/signal_bot/signals_log.txt 2>/dev/null | tail -15 || echo '(yok)'

echo '================================================================================'
echo '17) GitHub / git durumu'
echo '================================================================================'
cd /root/MINA_v2 && git rev-parse HEAD
cd /root/MINA_v2 && git log -1 --format='%H %s'
cd /root/MINA_v2 && git status --short
cd /root/MINA_v2 && git remote -v
cd /root/MINA_v2 && git branch -vv

echo '================================================================================'
echo '12-supplement: DCA limit iptal log satirlari'
echo '================================================================================'
grep -n 'DCA limit iptal' /root/MINA_v2/mina_bot.log 2>/dev/null | tail -20 || echo '(mina_bot DCA limit iptal yok)'
grep -n 'SLOT_BRIDGE' /root/MINA_v2/mina_bot.log 2>/dev/null | tail -30 || echo '(mina_bot SLOT_BRIDGE yok)'
journalctl --since '12 hours ago' --no-pager 2>/dev/null | grep -i SLOT_BRIDGE | tail -20 || echo '(journal SLOT_BRIDGE yok)'

echo '================================================================================'
echo '15-supplement: slot formül (tek balance call)'
echo '================================================================================'
/root/MINA_v2/venv/bin/python -c "
import os; os.chdir('/root/MINA_v2')
import sys; sys.path.insert(0,'/root/MINA_v2'); sys.path.insert(0,'/root/MINA_v2/backend')
from config import BinanceConfig, AccountManager
c=BinanceConfig().get_client(); a=AccountManager(c)
b=a.get_usdt_balance(); s=a.calculate_slot_size(); e=a.calculate_entry_amount()
print('balance=', b)
print('slot=balance/10=', s)
print('entry=slot*0.20=', e)
print('entry=slot/5=', s/5)
" 2>&1

echo '================================================================================'
echo '18) Disk ve bellek'
echo '================================================================================'
df -h /
free -h
ls -lh /root/MINA_v2/mina_bot.log /root/MINA_v2/signal_bot/merter_dca.log /root/MINA_v2/signal_bot/signals_log.txt 2>&1
du -sh /root/MINA_v2/mina_bot.log /root/MINA_v2/signal_bot/*.log 2>&1
du -sh /root/MINA_v2
ls -la /etc/logrotate.d/ 2>/dev/null | grep -i mina || echo 'logrotate.d mina: yok'
for f in /etc/logrotate.d/mina*; do [ -f "$f" ] && echo "--- $f ---" && cat "$f"; done
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
_, stdout, stderr = c.exec_command(SCRIPT, timeout=90)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(out)
    if err.strip():
        f.write("\nSTDERR:\n" + err)
print(f"Written {len(out)} chars to {out_path}")
c.close()
