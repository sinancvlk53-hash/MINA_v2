from backend.config import BinanceConfig, AccountManager
config = BinanceConfig()
client = config.get_client()
am = AccountManager(client)
s = am.get_account_summary()
print(s)
