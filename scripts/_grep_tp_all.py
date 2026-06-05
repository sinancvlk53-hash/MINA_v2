#!/usr/bin/env python3
import os,re,sys,paramiko,sqlite3
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
SYMS=["PARTIUSDT","DOTUSDT","ADAUSDT","XRPUSDT","ZROUSDT"]
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40','root',password=os.environ.get('MINA_SSH_PASS','REDACTED'),timeout=25)
for sym in SYMS:
    print('\n'+'#'*70)
    print(sym)
    _,o,_=c.exec_command(f"grep '{sym}' /root/MINA_v2/mina_bot.log | grep -E 'take_profit|trailing_stop|TP1|TP2|💰'",timeout=60)
    print(o.read().decode('utf-8',errors='replace') or '(mina_bot yok)')
c.close()
