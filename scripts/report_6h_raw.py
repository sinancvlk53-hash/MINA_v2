#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
"""Son 6 saat ham rapor — 2026-06-06 05:00–11:00 UTC."""
import os
import sys
import tempfile

import paramiko

HOST, USER = SSH_HOST, SSH_USER
PASS = require_ssh_pass()
R = "/root/MINA_v2"

REMOTE_PY = f"{R}/scripts/_report_positions_now.py"

POSITIONS_PY = '''#!/usr/bin/env python3
import os, sys
sys.path.insert(0, "/root/MINA_v2")
sys.path.insert(0, "/root/MINA_v2/backend")
os.chdir("/root/MINA_v2")
from dotenv import load_dotenv
load_dotenv("/root/MINA_v2/.env")
from config import BinanceConfig
client = BinanceConfig().get_client()
raw = client.futures_position_information()
print("symbol\\tside\\tentry\\tmark\\tpnl_usdt\\troe_pct")
for p in raw:
    amt = float(p.get("positionAmt") or 0)
    if amt == 0:
        continue
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(p.get("entryPrice") or 0)
    mark = float(p.get("markPrice") or 0)
    pnl = float(p.get("unRealizedProfit") or 0)
    iso = float(p.get("isolatedMargin") or p.get("isolatedWallet") or 0)
    lev = int(p.get("leverage") or 4)
    if iso <= 0 and entry > 0:
        iso = abs(amt) * entry / max(lev, 1)
    roe = (pnl / iso * 100) if iso > 0 else 0.0
    print(f"{p['symbol']}\\t{side}\\t{entry:.8f}\\t{mark:.8f}\\t{pnl:+.4f}\\t{roe:+.2f}")
'''

DERR_PY = f'''#!/usr/bin/env python3
import sqlite3
conn = sqlite3.connect("{R}/mina_trading_journal.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT symbol, side, close_reason, pnl_usdt, close_time FROM trades "
    "WHERE close_time >= '2026-06-06 05:00' ORDER BY close_time"
).fetchall()
print("symbol\\tside\\tclose_reason\\tpnl_usdt\\tclose_time")
for r in rows:
    print(f"{{r['symbol']}}\\t{{r['side']}}\\t{{r['close_reason']}}\\t{{r['pnl_usdt']}}\\t{{r['close_time']}}")
conn.close()
'''

SECTIONS = [
    (
        "1) MOTOR LOG (kullanıcı grep)",
        f"grep -E 'take_profit|trailing_stop|defense|stop_loss|açıldı|kapandı' "
        f"{R}/mina_bot.log 2>/dev/null | grep '2026-06-06 0[5-9]\\|2026-06-06 1[0-1]' || true",
    ),
    (
        "1c) MOTOR LOG — penceredeki tüm satır sayısı + son 20 satır",
        f"grep -E '2026-06-06 0[5-9]:|2026-06-06 10:|2026-06-06 11:0' {R}/mina_bot.log 2>/dev/null | "
        "tee /tmp/motor_6h.log | wc -l; echo '--- son 20 ---'; tail -20 /tmp/motor_6h.log 2>/dev/null || true",
    ),
    (
        "2) DERR kapanan işlemler",
        f"{R}/venv/bin/python {R}/scripts/_report_derr_closes.py",
    ),
    (
        "3) MERTER DCA LOG (kullanıcı grep)",
        f"grep '2026-06-06T0[5-9]\\|2026-06-06T1[0-1]' {R}/signal_bot/merter_dca.log 2>/dev/null || "
        f"(test -f {R}/signal_bot/merter_dca.log && echo '(eşleşen satır yok)' || echo 'merter_dca.log yok')",
    ),
    (
        "4) BİNANCE AÇIK POZİSYONLAR (şu an)",
        f"{R}/venv/bin/python {REMOTE_PY}",
    ),
]


def run(c, cmd, timeout=120):
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return (
        stdout.read().decode("utf-8", errors="replace"),
        stderr.read().decode("utf-8", errors="replace"),
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()
    try:
        sftp.stat(f"{R}/scripts")
    except FileNotFoundError:
        c.exec_command(f"mkdir -p {R}/scripts")
    with sftp.open(REMOTE_PY, "w") as f:
        f.write(POSITIONS_PY)
    with sftp.open(f"{R}/scripts/_report_derr_closes.py", "w") as f:
        f.write(DERR_PY)
    sftp.close()

    for title, cmd in SECTIONS:
        print("=" * 80)
        print(title)
        print("=" * 80)
        print(f"$ {cmd}")
        print("-" * 80)
        out, err = run(c, cmd)
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err.strip():
            print(err, end="" if err.endswith("\n") else "\n")
        if not out.strip() and not err.strip():
            print("(çıktı yok)")
        print()

    c.close()


if __name__ == "__main__":
    main()
