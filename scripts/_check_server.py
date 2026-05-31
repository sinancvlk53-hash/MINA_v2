import paramiko, os, time

HOST = "178.105.150.40"
USER = "root"
PASS = "REDACTED"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=10)

cmds = [
    ("backtest.py var mi?",    "ls -lh /root/MINA_v2/backtest.py 2>&1"),
    ("ei_signals.json var mi?","ls -lh /root/MINA_v2/signal_bot/history/ei_signals.json 2>&1"),
    ("Python calisiyor mu?",   "pgrep -a python 2>&1"),
    ("backtest.log",           "cat /tmp/backtest.log 2>&1 | tail -10"),
]

for label, cmd in cmds:
    _, out, _ = c.exec_command(cmd)
    result = out.read().decode().strip()
    print(f"\n[{label}]\n{result}")

c.close()
