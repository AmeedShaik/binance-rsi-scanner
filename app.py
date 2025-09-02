import streamlit as st
from binance import Client
import pandas as pd
import plotly.graph_objects as go

# Public client (no keys)
client = Client()

st.title("BTCUSDT Candlestick Chart")

# Fetch data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1MINUTE, "1 hour ago UTC")

df = pd.DataFrame(klines, columns=[
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "qav", "num_trades", "taker_base_vol",
    "taker_quote_vol", "ignore"
])
df = df[["timestamp", "open", "high", "low", "close"]]
df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)

# Chart
fig = go.Figure(data=[go.Candlestick(
    x=pd.to_datetime(df["timestamp"], unit="ms"),
    open=df["open"], high=df["high"],
    low=df["low"], close=df["close"]
)])
fig.update_layout(title="BTCUSDT 1m Candlestick (last 1h)", xaxis_rangeslider_visible=False)

st.plotly_chart(fig, use_container_width=True)
