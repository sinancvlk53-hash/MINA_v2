#!/usr/bin/env python3
import os, paramiko
from datetime import datetime, timezone
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40','root',password=os.environ.get('MINA_SSH_PASS','REDACTED'),timeout=25)
_,o,_=c.exec_command("""
/root/MINA_v2/venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0,'/root/MINA_v2')
sys.path.insert(0,'/root/MINA_v2/backend')
from dotenv import load_dotenv
load_dotenv('/root/MINA_v2/.env')
from config import BinanceConfig
from datetime import datetime, timezone
client = BinanceConfig().get_client()
trades = client.futures_account_trades(symbol='PARTIUSDT', limit=30)
print('PARTIUSDT son 30 trade:')
print(f"{'time':<22} {'side':<5} {'pos':<6} {'qty':>8} {'price':>10} {'pnl':>10}")
for t in reversed(trades):
    ts = datetime.fromtimestamp(t['time']/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f"{ts:<22} {t['side']:<5} {t.get('positionSide',''):<6} {float(t['qty']):>8.1f} {float(t['price']):>10.6f} {float(t.get('realizedPnl',0)):>10.4f}")
PY
""",timeout=60)
print(o.read().decode('utf-8',errors='replace'))
c.close()
