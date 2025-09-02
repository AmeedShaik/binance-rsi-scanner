from binance import Client

# Public client (no keys needed for price data)
client = Client()

# Works even if Streamlit Cloud blocks authenticated API calls
print(client.get_symbol_ticker(symbol="BTCUSDT"))
