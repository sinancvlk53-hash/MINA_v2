#!/usr/bin/env python3
import os
import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
LOCAL = os.path.dirname(os.path.abspath(__file__))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
for name in ("scan_haluk_today.py",):
    sftp.put(os.path.join(LOCAL, name), f"/root/MINA_v2/scripts/{name}")
sftp.close()

cmds = [
    "/root/MINA_v2/venv/bin/python -c \""
    "import glob,os; "
    "from signal_bot.haluk_pdf_parser import parse_haluk_pdf; "
    "from signal_bot.macro_levels_store import load_macro_levels; "
    "pdfs=glob.glob('/root/MINA_v2/signal_bot/pdfs/*.pdf'); "
    "p=max(pdfs,key=os.path.getmtime) if pdfs else None; "
    "print('PDF',p); "
    "parse_haluk_pdf(p) if p else None; "
    "import json; print(json.dumps(load_macro_levels(),ensure_ascii=False)[:2000])"
    "\"",
    "/root/MINA_v2/venv/bin/python /root/MINA_v2/scripts/scan_haluk_today.py",
]
for cmd in cmds:
    print("\n>>>", cmd[:80], "...")
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:500])
c.close()
