#!/usr/bin/env python3
import subprocess
services = ["mina-engine","mina-listener","mina-merter-dca","mina-queue-watcher","mina-dashboard-ws","mina-dashboard-vite"]
for s in services:
    print(f"=== {s}.service ===")
    r = subprocess.run(["systemctl","cat",f"{s}.service"], capture_output=True, text=True)
    print(r.stdout or r.stderr)
