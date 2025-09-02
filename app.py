import streamlit as st
from binance import Client

api_key = "EjYRoIIs9cDVfBghQPY3rTQvh9yi5KjOVbK0C2vEiGT6MFz3HEtxvXyLtqlB7rlL"
api_secret = "O02JXtAnPsjGvrgpbtdhBioDGylOC3qoP8PqZRIyJVwnuVWTeZqMKuWR2zATIIoT"

client = Client(api_key, api_secret)  # Live Binance

st.title("Binance Live Test")

try:
    ticker = client.get_symbol_ticker(symbol="BTCUSDT")
    st.write("✅ Live connection successful!")
    st.write("BTCUSDT Price:", ticker["price"])
except Exception as e:
    st.error(f"Error: {e}")
