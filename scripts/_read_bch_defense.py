#!/usr/bin/env python3
import os, sys, json, paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40', username='root', password=os.environ.get('MINA_SSH_PASS','REDACTED'), timeout=25)
cmds = [
    ('defense_levels.json BCH', 'cat /root/MINA_v2/defense_levels.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({k:v for k,v in d.items() if \"BCH\" in k}, indent=2))"'),
    ('initial_entry BCH', 'cat /root/MINA_v2/initial_entry_prices.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({k:v for k,v in d.items() if \"BCH\" in k}, indent=2))"'),
    ('position_state BCH', 'cat /root/MINA_v2/mina_position_state.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get(\"BCHUSDT\", d.get(\"positions\",{}).get(\"BCHUSDT\",\"?\")), indent=2) if isinstance(d,dict) else d)"'),
    ('journal BCH defense', '''/root/MINA_v2/venv/bin/python - <<'PY'
import sqlite3, json
c=sqlite3.connect("/root/MINA_v2/mina_trading_journal.db")
c.row_factory=sqlite3.Row
r=c.execute("SELECT id,defense_triggered,defense_prices,weighted_avg_price,open_price,status FROM trades WHERE symbol='BCHUSDT' AND status='open'").fetchone()
print(dict(r) if r else "no open trade")
PY'''),
]
for title, cmd in cmds:
    print('='*60)
    print(title)
    print('='*60)
    _, out, err = c.exec_command(cmd, timeout=30)
    print(out.read().decode('utf-8', errors='replace') or '(bos)')
    e = err.read().decode('utf-8', errors='replace')
    if e.strip(): print('stderr:', e)
c.close()
