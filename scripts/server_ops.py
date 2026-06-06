#!/usr/bin/env python3
"""Sunucu ops: git sync, cron yedek, logrotate."""
import os
import sys

import paramiko

HOST, USER = "178.105.150.40", "root"
PASS = os.environ.get("MINA_SSH_PASS", "REDACTED")
REMOTE = "/root/MINA_v2"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(client, cmd: str, timeout: int = 120) -> str:
    print(f">>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(err, file=sys.stderr)
    return out + err


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = c.open_sftp()

    # Ops dosyalarını yükle
    run(c, f"mkdir -p {REMOTE}/ops")
    for rel in ("ops/backup_mina.sh", "ops/logrotate_mina"):
        lp = os.path.join(LOCAL, rel.replace("/", os.sep))
        rp = f"{REMOTE}/{rel}"
        sftp.put(lp, rp)
        if rel.endswith(".sh"):
            run(c, f"chmod +x {rp}")

    run(c, f"mkdir -p /root/backups")
    run(c, f"cp {REMOTE}/ops/logrotate_mina /etc/logrotate.d/mina")
    run(c, "sed -i 's/\\r$//' /etc/logrotate.d/mina")
    run(c, "logrotate -d /etc/logrotate.d/mina 2>&1 | head -20 || true")

    cron_line = "0 2 * * * /root/MINA_v2/ops/backup_mina.sh >> /root/backups/backup.log 2>&1"
    run(
        c,
        f"(crontab -l 2>/dev/null | grep -v backup_mina.sh; echo '{cron_line}') | crontab -",
    )
    run(c, "crontab -l | grep backup_mina || true")

    # Git senkron (repo-local identity, config dosyasına yazmaz)
    git_user = os.environ.get("MINA_GIT_USER", "MINA Server")
    git_email = os.environ.get("MINA_GIT_EMAIL", "mina-server@local")
    run(c, f"cd {REMOTE} && git add -A")
    run(
        c,
        f'cd {REMOTE} && git -c user.name="{git_user}" -c user.email="{git_email}" '
        f'commit -m "chore: sunucu senkron - tüm değişiklikler" || true',
    )
    push_out = run(c, f"cd {REMOTE} && git remote -v && git push origin HEAD 2>&1 || true")
    if "fatal:" in push_out.lower() and "could not read" in push_out.lower():
        print("WARN: git push failed — sunucuda GitHub kimlik bilgisi/SSH key gerekebilir")

    sftp.close()
    c.close()
    print("Server ops done.")


if __name__ == "__main__":
    main()
