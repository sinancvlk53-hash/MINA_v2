#!/usr/bin/env python3
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paramiko
from mina_ssh import connect_paramiko
cmds = [
("approval 15:38-15:45", "journalctl -u mina-approval-bot --since '2026-06-11 15:38' --until '2026-06-11 15:45' --no-pager 2>&1"),
("pdf-listener 15:38-15:45", "journalctl -u mina-pdf-listener --since '2026-06-11 15:38' --until '2026-06-11 15:45' --no-pager 2>&1"),
("queue files", "ls -la /root/MINA_v2/signal_bot/ht_signals_queue.json /root/MINA_v2/signal_bot/raw_signal_queue.json 2>&1"),
("listener pdf log", "grep -i 'HALUK PDF\\|HALUK VISUAL\\|ht_pdf\\|QUEUE' /root/MINA_v2/signal_bot/listener.log 2>/dev/null | tail -30 || echo yok"),
]
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); connect_paramiko(c)
for t,cmd in cmds:
    print("===", t, "===")
    _,o,e=c.exec_command(cmd,timeout=90)
    out=o.read().decode("utf-8",errors="replace")
    print(out[-8000:] if len(out)>8000 else out)
    err=e.read().decode()
    if err.strip(): print("ERR", err)
c.close()
