#!/usr/bin/env python3
import sys, os, json
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); connect_paramiko(c)
_,o,e=c.exec_command("cat /root/MINA_v2/signal_bot/raw_signal_queue.json", timeout=30)
print(o.read().decode("utf-8", errors="replace")[:12000])
c.close()
