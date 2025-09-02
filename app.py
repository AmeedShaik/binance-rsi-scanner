from binance import Client, ThreadedWebsocketManager
import pandas as pd
import plotly.graph_objects as go

# ===============================
# 1. Setup API keys & client
# ===============================
api_key = "EjYRoIIs9cDVfBghQPY3rTQvh9yi5KjOVbK0C2vEiGT6MFz3HEtxvXyLtqlB7rlL"
api_secret = "O02JXtAnPsjGvrgpbtdhBioDGylOC3qoP8PqZRIyJVwnuVWTeZqMKuWR2zATIIoT"

client = Client(api_key, api_secret)

# Uncomment if you want to use Testnet instead of live
# client.API_URL = 'https://testnet.binance.vision/api'

# ===============================
# 2. Fetch historical data
# ===============================
klines = client.get_historical_klines(
    "BTCUSDT", Client.KLINE_INTERVAL_1MINUTE, "1 hour ago UTC"
)

# Convert to DataFrame
df = pd.DataFrame(klines, columns=[
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "qav", "num_trades", "taker_base_vol",
    "taker_quote_vol", "ignore"
])

# Keep only relevant columns
df = df[["timestamp", "open", "high", "low", "close", "volume"]]
df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)

# ===============================
# 3. Plot candlestick chart
# ===============================
fig = go.Figure(data=[go.Candlestick(
    x=pd.to_datetime(df["timestamp"], unit="ms"),
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    name="BTCUSDT"
)])

fig.update_layout(
    title="BTCUSDT Live Candlestick (1m)",
    xaxis_title="Time",
    yaxis_title="Price (USDT)",
    xaxis_rangeslider_visible=False
)

fig.show()

# ===============================
# 4. WebSocket for live prices
# ===============================
def handle_kline(msg):
    if msg['e'] == 'kline':
        k = msg['k']
        close = k['c']
        print(f"Live BTC Close: {close} USDT")

twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
twm.start()

# Stream 1-minute candles for BTCUSDT
twm.start_kline_socket(callback=handle_kline, symbol='BTCUSDT', interval=Client.KLINE_INTERVAL_1MINUTE)
