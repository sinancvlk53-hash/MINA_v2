#!/usr/bin/env python3

import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import os, paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, SSH_USER, password=require_ssh_pass(),timeout=25)
syms = 'PARTIUSDT|DOTUSDT|ADAUSDT|XRPUSDT|ZROUSDT'
cmd = f"grep -E '{syms}' /root/MINA_v2/mina_bot.log | grep -iE 'take_profit|TP1|TP2|trailing|💰|Giriş|open|entry' | tail -80"
_,o,_=c.exec_command(cmd,timeout=60)
print(o.read().decode('utf-8',errors='replace'))
c.close()
