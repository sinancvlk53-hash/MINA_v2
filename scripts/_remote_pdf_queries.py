#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paramiko
from mina_ssh import connect_paramiko, SSH_HOST, SSH_USER

REMOTE = r"""
echo "========== 1. Bugun gelen PDF'ler =========="
ls -lt /root/MINA_v2/signal_bot/pdfs/ 2>/dev/null | head -10 || echo "(pdfs klasoru yok)"

echo ""
echo "========== 2. PDF / haluk log (mina_bot.log) =========="
grep -i "pdf\|haluk\|visual\|signal\|extract" /root/MINA_v2/mina_bot.log 2>/dev/null | tail -30 || echo "(eslesme yok veya log yok)"

echo ""
echo "========== 3. ht_signals_queue.json =========="
if [ -f /root/MINA_v2/signal_bot/ht_signals_queue.json ]; then
  python3 -m json.tool /root/MINA_v2/signal_bot/ht_signals_queue.json 2>/dev/null | tail -50 || cat /root/MINA_v2/signal_bot/ht_signals_queue.json | tail -50
else
  echo "DOSYA YOK VEYA BOŞ"
fi

echo ""
echo "========== 4. ht_pdf_basari_orani =========="
cd /root/MINA_v2 && python3 << 'PY4'
import sqlite3
conn = sqlite3.connect('mina_trading_journal.db')
try:
    rows = conn.execute('SELECT * FROM ht_pdf_basari_orani ORDER BY created_at DESC LIMIT 10').fetchall()
    cols = [d[0] for d in conn.execute('PRAGMA table_info(ht_pdf_basari_orani)').fetchall()]
    print(f'Kayit sayisi: {len(rows)}')
    for r in rows:
        for c, v in zip(cols, r):
            print(f'{c}: {v}')
        print('---')
except Exception as e:
    print(f'Hata: {e}')
conn.close()
PY4

echo ""
echo "========== 5. approval_bot PDF grep =========="
grep -n "process_new_pdf\|haluk_pdf\|extract_trading\|visual" /root/MINA_v2/signal_bot/approval_bot.py 2>/dev/null | head -20 || echo "(dosya yok)"

echo ""
echo "========== 6. Son PDF manuel parse =========="
cd /root/MINA_v2 && /root/MINA_v2/venv/bin/python3 << 'PY6'
import sys
import glob
sys.path.insert(0, '/root/MINA_v2')
try:
    from signal_bot.haluk_pdf_visual import extract_trading_signals
    pdfs = sorted(glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'))
    if not pdfs:
        print('PDF bulunamadi')
    else:
        pdf = pdfs[-1]
        print(f'PDF: {pdf}')
        signals = extract_trading_signals(pdf)
        print(f'Sinyal sayisi: {len(signals)}')
        for s in signals:
            print(s)
except Exception as e:
    import traceback
    print(f'Hata: {e}')
    traceback.print_exc()
PY6
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_paramiko(c, host=SSH_HOST, user=SSH_USER, timeout=30)
    _, stdout, stderr = c.exec_command(REMOTE, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stderr.buffer.write(("STDERR: " + err).encode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
