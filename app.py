""" Patched app file for binance-rsi-scanner

This file contains:

fetch_klines_with_fallback(...) that tries authenticated python-binance, falls back to Binance public REST, then CoinGecko (BTC only) if needed.

A small Streamlit-based UI that demonstrates usage and shows which data source is being used. It also calculates a simple RSI for demonstration.


HOW TO USE:

1. Replace your current kline-fetching logic with from app_patched import fetch_klines_with_fallback or copy the fetch_klines_with_fallback and klines_to_df functions directly into your existing app.py.


2. Keep your existing trading logic separate. This patched file is intentionally minimal so it won't overwrite your full trading code.



Note: Do NOT hardcode real API keys into code. Use environment variables or Streamlit secrets. """

import os import time import traceback import requests import pandas as pd

try importing python-binance but allow running without it

try: from binance.client import Client from binance.exceptions import BinanceAPIException _HAS_BINANCE = True except Exception: Client = None BinanceAPIException = Exception _HAS_BINANCE = False

--------- KLINES + FALLBACK HELPERS ---------

def klines_to_df(klines): """Convert Binance-style kline list to DataFrame.""" cols = [ "open_time","open","high","low","close","volume","close_time", "qav","num_trades","taker_base_vol","taker_quote_vol","ignore" ] df = pd.DataFrame(klines, columns=cols) # convert timestamps if not df.empty: df["open_time"] = pd.to_datetime(df["open_time"], unit="ms") try: df["close_time"] = pd.to_datetime(df["close_time"], unit="ms") except Exception: pass for c in ["open","high","low","close","volume"]: if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce") return df

def fetch_klines_with_fallback(symbol="BTCUSDT", interval="1h", limit=500, api_key=None, api_secret=None, verbose=True): """ Attempt order of data sources: 1) Authenticated python-binance client (if keys provided and python-binance installed) 2) Binance public REST (no auth) 3) CoinGecko OHLC (BTC only, limited intervals)

Returns: (df, source_str)
"""
# 1) try authenticated python-binance client
if api_key and api_secret and _HAS_BINANCE:
    try:
        client = Client(api_key, api_secret)
        kl = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = klines_to_df(kl)
        if verbose:
            print("Using binance-auth (authenticated python-binance)")
        return df, "binance-auth"
    except BinanceAPIException as e:
        txt = str(e)
        if verbose:
            print("BinanceAPIException when using authenticated client:", txt)
        # specifically detect the restricted-location message
        if "restricted location" in txt.lower() or "service unavailable from a restricted location" in txt.lower():
            if verbose:
                print("Detected restricted location error. Falling back to public endpoints.")
        # fall through to public
    except Exception as e:
        if verbose:
            print("Error using authenticated client:", e)
            traceback.print_exc()
        # fall through

# 2) public Binance REST
try:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    kl = r.json()
    df = klines_to_df(kl)
    if verbose:
        print("Using binance-public (public REST)")
    return df, "binance-public"
except Exception as e:
    if verbose:
        print("Public Binance klines failed:", e)
        traceback.print_exc()

# 3) CoinGecko fallback for BTC only (limited precision/intervals)
try:
    if symbol.upper().startswith("BTC"):
        cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
        # CoinGecko days param: 1/7/14/30/90/180/365/max
        days = 30
        r = requests.get(cg_url, params={"vs_currency":"usd","days":days}, timeout=10)
        r.raise_for_status()
        data = r.json()  # [ [timestamp, open, high, low, close], ...]
        df = pd.DataFrame(data, columns=["open_time","open","high","low","close"])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["volume"] = None
        if verbose:
            print("Using coingecko fallback (BTC OHLC)")
        return df, "coingecko"
except Exception as e:
    if verbose:
        print("CoinGecko fallback failed:", e)
        traceback.print_exc()

raise RuntimeError("Failed to fetch klines from Binance (auth/public) and CoinGecko fallback.")

--------- SMALL RSI UTIL (for demo) ---------

def compute_rsi(series, period=14): """Compute RSI for a pandas Series of prices.""" delta = series.diff() up = delta.clip(lower=0) down = -1 * delta.clip(upper=0) ma_up = up.ewm(com=(period - 1), adjust=False).mean() ma_down = down.ewm(com=(period - 1), adjust=False).mean() rs = ma_up / ma_down rsi = 100 - (100 / (1 + rs)) return rsi

--------- STREAMLIT DEMO APP (optional) ---------

This block provides a simple UI to test the fallback. If you already have

a full Streamlit app, copy the fetch_klines_with_fallback and compute_rsi

functions into it instead of running this demo.

if name == "main": # If run as a script, start a minimal Streamlit app try: import streamlit as st except Exception: raise RuntimeError("streamlit is required to run the demo. Install with: pip install streamlit")

st.set_page_config(page_title="Binance RSI Scanner - Fallback Demo", layout="wide")

st.title("Binance RSI Scanner — Fallback-enabled demo")
col1, col2 = st.columns([2,1])

with col1:
    symbol = st.text_input("Symbol (e.g. BTCUSDT)", value="BTCUSDT")
    interval = st.selectbox("Interval", ["1m","5m","15m","1h","4h","1d"], index=3)
    limit = st.number_input("Klines limit", min_value=10, max_value=1000, value=200)

    st.write("---")
    st.write("**API Keys (optional)** — leave blank to use public data only")
    bin_key = st.text_input("BINANCE_API_KEY", type="password")
    bin_secret = st.text_input("BINANCE_SECRET", type="password")

    if st.button("Fetch and compute RSI"):
        with st.spinner("Fetching klines..."):
            try:
                api_key = bin_key.strip() or None
                api_secret = bin_secret.strip() or None
                df, source = fetch_klines_with_fallback(symbol, interval, limit, api_key, api_secret, verbose=False)
                st.success(f"Data source: {source}")

                if df is None or df.empty:
                    st.warning("No data returned.")
                else:
                    # compute RSI if close exists
                    if "close" in df.columns:
                        df["rsi"] = compute_rsi(df["close"].astype(float))
                        st.dataframe(df[["open_time","open","high","low","close","rsi"]].tail(100))
                    else:
                        st.dataframe(df.tail(50))
            except Exception as e:
                st.error(f"Failed to fetch klines: {e}")
                st.exception(e)

with col2:
    st.write("## Notes & Actions")
    st.write("- If you see `binance-auth` blocked due to location, the app will use public data instead.")
    st.write("- For real trading (orders), ensure your account & IP are allowed; contact Binance support if needed.")
    st.write("- Revoke any tokens you shared accidentally (ngrok, API keys).")

st.write("\n---\nThis is a small demo with fallback logic. For production, integrate the fetch_klines_with_fallback into your existing app logic, and ensure you never hardcode secrets.")

