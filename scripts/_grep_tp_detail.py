#!/usr/bin/env python3
import os, paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('178.105.150.40','root',password=os.environ.get('MINA_SSH_PASS','REDACTED'),timeout=25)
syms = 'PARTIUSDT|DOTUSDT|ADAUSDT|XRPUSDT|ZROUSDT'
cmd = f"grep -E '{syms}' /root/MINA_v2/mina_bot.log | grep -iE 'take_profit|TP1|TP2|trailing|💰|Giriş|open|entry' | tail -80"
_,o,_=c.exec_command(cmd,timeout=60)
print(o.read().decode('utf-8',errors='replace'))
c.close()
