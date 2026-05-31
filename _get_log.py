import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("178.105.150.40", username="root", password="REDACTED", timeout=10)

_, out, _ = c.exec_command("cat /tmp/backtest.log")
print(out.read().decode())

# backtest_results.json indir
sftp = c.open_sftp()
sftp.get("/root/MINA_v2/signal_bot/history/backtest_results.json",
         "signal_bot/history/backtest_results.json")
sftp.close()
print("backtest_results.json indirildi.")
c.close()
