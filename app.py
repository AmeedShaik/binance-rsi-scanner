from binance import Client

api_key = "EjYRoIIs9cDVfBghQPY3rTQvh9yi5KjOVbK0C2vEiGT6MFz3HEtxvXyLtqlB7rlL"
api_secret = "O02JXtAnPsjGvrgpbtdhBioDGylOC3qoP8PqZRIyJVwnuVWTeZqMKuWR2zATIIoT"

# Important: DO NOT set testnet=True or change API_URL
client = Client(api_key, api_secret)

# Test connection
print(client.get_server_time())
print(client.get_symbol_ticker(symbol="BTCUSDT"))
