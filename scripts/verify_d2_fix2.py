#!/usr/bin/env python3
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mina_ssh import require_ssh_pass, SSH_HOST, SSH_USER
import paramiko
pwd = require_ssh_pass()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, username='root', password=pwd, timeout=60, banner_timeout=60)
time.sleep(35)
cmds = [
    "journalctl -u mina-engine.service --since '5 min ago' --no-pager | tail -50",
    "grep FAILED /root/MINA_v2/mina_bot.log | tail -10",
    "grep 'icra tamamlanmadi' /root/MINA_v2/mina_bot.log | tail -5",
    "grep 'D2 ekleme' /root/MINA_v2/mina_bot.log | tail -5",
    "grep 'D2 y' /root/MINA_v2/mina_bot.log | tail -5",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=60)
    print(f"$ {cmd}\n{o.read().decode()}\n")
c.close()
