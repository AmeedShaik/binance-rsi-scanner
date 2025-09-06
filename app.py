# dependencies: requests, pandas, python-binance (optional)
from binance.client import Client
from binance.exceptions import BinanceAPIException
import requests
import pandas as pd
import traceback

def klines_to_df(klines):
    """Convert Binance klines list to pandas DataFrame."""
    cols = ["open_time","open","high","low","close","volume","close_time",
            "qav","num_trades","taker_base_vol","taker_quote_vol","ignore"]
    df = pd.DataFrame(klines, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c])
    return df

def fetch_klines_with_fallback(symbol="BTCUSDT", interval="1h", limit=500, api_key=None, api_secret=None):
    """
    Try authenticated Binance client first. On location-restriction error,
    fall back to public Binance REST klines (no auth). If that fails, fall
    back to CoinGecko public API for basic OHLC (if available).
    Returns a pandas DataFrame of OHLCV.
    """
    # 1) Try authenticated python-binance client (if keys provided)
    if api_key and api_secret:
        try:
            client = Client(api_key, api_secret)
            kl = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            df = klines_to_df(kl)
            df.attrs['source'] = 'binance-auth'
            return df
        except BinanceAPIException as e:
            # detect location restriction text (safe to check substring)
            txt = str(e)
            if "Service unavailable from a restricted location" in txt or "restricted location" in txt.lower():
                print("Binance authenticated API blocked due to restricted location. Falling back to public data.")
            else:
                # other Binance API errors we might still want to fallback for
                print("Binance APIException:", e)
            # fall through to public
        except Exception as e:
            print("Binance client error (non-BinanceAPIException):", e)
            traceback.print_exc()

    # 2) Try public Binance REST klines (no API key)
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        kl = r.json()
        df = klines_to_df(kl)
        df.attrs['source'] = 'binance-public'
        return df
    except Exception as e:
        print("Public Binance klines failed:", e)
        traceback.print_exc()

    # 3) Optional: fallback to CoinGecko (limited OHLC support)
    try:
        # CoinGecko supports OHLC for limited intervals; convert if possible
        cg_symbol = symbol.replace("USDT", "usd").lower()
        # coin id lookup would be needed — here is a basic try for bitcoin only:
        if symbol.upper().startswith("BTC"):
            cg_url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
            # CoinGecko OHLC requires vs_currency and days (1/7/14/30/90/180/365/max)
            days = 30
            r = requests.get(cg_url, params={"vs_currency":"usd","days":days}, timeout=10)
            r.raise_for_status()
            data = r.json()
            # data: [ [timestamp, open, high, low, close], ... ]
            df = pd.DataFrame(data, columns=["open_time","open","high","low","close"])
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df["volume"] = None
            df.attrs['source'] = 'coingecko'
            return df
    except Exception as e:
        print("CoinGecko fallback failed:", e)

    # If all fail, raise
    raise RuntimeError("Failed to fetch klines from Binance (auth/public) and CoinGecko fallback.")

# Example usage in your app:
# df = fetch_klines_with_fallback("BTCUSDT","1h",200, api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_SECRET"))
# print("Data source:", df.attrs.get('source'))