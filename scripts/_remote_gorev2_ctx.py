import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", username="root", password="REDACTED", timeout=15)
py = r"""
path = '/root/MINA_v2/mina_bot.log'
lines = open(path, 'r', encoding='utf-8', errors='replace').read().splitlines()
idx = [i for i, l in enumerate(lines) if 'ERROR' in l or 'CRITICAL' in l]
for i in idx[-5:]:
    block = lines[i:i+8]
    print('===== block at line', i+1, '=====')
    for l in block:
        print(l)
"""
_, out, err = c.exec_command(f"python3 -c {repr(py)}", timeout=120)
sys.stdout.write(out.read().decode("utf-8", errors="replace"))
c.close()
