#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 tetik koşulu + motor durumu."""
import json, os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko

REMOTE = "/root/MINA_v2"
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username=SSH_USER, password=pwd, timeout=60, banner_timeout=60)

cmds = [
    "systemctl is-active mina-engine.service",
    "tail -5 /root/MINA_v2/mina_bot.log",
    f"{REMOTE}/venv/bin/python -c \""
    "import json,requests; "
    "init=json.load(open('/root/MINA_v2/initial_entry_prices.json')); "
    "defense=json.load(open('/root/MINA_v2/defense_levels.json')); "
    "syms=[k.replace('_LONG','') for k in init]; "
    "prices={}; "
    "for s in syms: "
    " r=requests.get('https://fapi.binance.com/fapi/v1/ticker/price',params={'symbol':s},timeout=10); "
    " prices[s]=float(r.json()['price']); "
    "print('MARK vs D1 threshold (entry*0.95):'); "
    "for k,v in init.items(): "
    " sym=k.replace('_LONG',''); "
    " mark=prices.get(sym,0); "
    " d1=v*0.95; "
    " fake=v*1.06; "
    " fake_d1=fake*0.95; "
    " dl=defense.get(k,0); "
    " print(f'{k} entry={v} mark={mark} d1_thr={d1:.6f} fake_entry={fake:.6f} fake_d1_thr={fake_d1:.6f} defense={dl} trigger_now={mark<=d1} trigger_fake={mark<=fake_d1}')\"",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    print(f"$ {cmd}\n{o.read().decode()}{e.read().decode()}")
c.close()
