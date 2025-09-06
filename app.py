# streamlit_btc_ui.py
import time
import io
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from textwrap import dedent

# Try import ccxt (optional)
try:
    import ccxt
    _HAS_CCXT = True
except Exception:
    ccxt = None
    _HAS_CCXT = False

# ---------- Helpers: resilient fetcher (ccxt tries, then CoinGecko) ----------
def fetch_ohlcv_via_ccxt(exchange_id, symbol_variants, timeframe="1h", limit=200):
    last_exc = None
    if not _HAS_CCXT:
        raise RuntimeError("ccxt not installed")
    if not hasattr(ccxt, exchange_id):
        raise AttributeError(f"ccxt has no exchange named '{exchange_id}'")
    Exch = getattr(ccxt, exchange_id)
    ex = Exch({"enableRateLimit": True})
    ex.timeout = 30000
    for sym in symbol_variants:
        try:
            ohlcv = ex.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as e:
            last_exc = e
            # continue trying others
            time.sleep(0.15)
    raise last_exc

def fetch_btc_ohlcv_resilient(timeframe="1h", limit=200, try_exchanges=None):
    if try_exchanges is None:
        try_exchanges = [
            "kraken", "bitstamp", "bitfinex", "coinbasepro", "coinbase", "gemini",
            "huobipro", "okx", "kucoin", "gate", "mexc", "whitebit"
        ]
    common_variants = ["BTC/USDT", "BTC/USD", "BTC/USDT:USDT", "BTC/USDT:USD"]
    if _HAS_CCXT:
        for exch in try_exchanges:
            try:
                if not hasattr(ccxt, exch):
                    continue
                variants = common_variants.copy()
                if exch in ("coinbasepro", "coinbase", "gemini"):
                    variants = ["BTC/USD", "BTC-USD", "BTC/USDT"]
                if exch == "kraken":
                    variants = ["BTC/USD", "XBT/USD", "BTC/USDT"]
                if exch == "bitfinex":
                    variants = ["BTC/USD", "BTC/USDT", "tBTCUSD"]
                df = fetch_ohlcv_via_ccxt(exch, variants, timeframe=timeframe, limit=limit)
                return df, f"ccxt:{exch}"
            except Exception as e:
                # log and continue
                st.write(f"Exchange {exch} failed: {repr(e)}")
                continue
    # Fallback to CoinGecko
    df = fetch_btc_ohlcv_coingecko(timeframe=timeframe, limit=limit)
    return df, "coingecko"

def fetch_btc_ohlcv_coingecko(timeframe="1h", limit=200, days=7):
    tf_to_mins = {"1m":1, "5m":5, "15m":15, "30m":30, "1h":60, "4h":240, "1d":1440}
    if timeframe not in tf_to_mins:
        raise ValueError("Unsupported timeframe for CoinGecko fallback")
    minutes = tf_to_mins[timeframe]
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency":"usd", "days": days}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    prices = js.get("prices", [])
    if not prices:
        raise RuntimeError("CoinGecko returned no prices")
    pdf = pd.DataFrame(prices, columns=["timestamp_ms","price"])
    pdf["timestamp"] = pd.to_datetime(pdf["timestamp_ms"], unit="ms")
    pdf = pdf.set_index("timestamp").drop(columns=["timestamp_ms"])
    ohlc = pdf["price"].resample(f"{minutes}T").ohlc().dropna()
    ohlc["volume"] = None
    ohlc = ohlc.reset_index().rename(columns={"open":"open","high":"high","low":"low","close":"close"})
    if len(ohlc) > limit:
        ohlc = ohlc.tail(limit).reset_index(drop=True)
    return ohlc

# ---------- Small RSI util ----------
def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=(period - 1), adjust=False).mean()
    ma_down = down.ewm(com=(period - 1), adjust=False).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ---------- Streamlit UI ----------
st.set_page_config(page_title="BTC OHLC Viewer", layout="wide")
st.title("BTC OHLC Viewer — resilient data source + RSI")

with st.sidebar:
    st.header("Fetch settings")
    timeframe = st.selectbox("Timeframe", ["1m","5m","15m","30m","1h","4h","1d"], index=4)
    limit = st.number_input("Candles (limit)", min_value=10, max_value=2000, value=200, step=10)
    days = st.number_input("CoinGecko days (for fallback)", min_value=1, max_value=365, value=7)
    st.markdown("---")
    st.write("Optional: enable ccxt (if installed) to try exchange-accurate candles.")
    if _HAS_CCXT:
        st.success("ccxt is available")
    else:
        st.warning("ccxt not installed — app will use CoinGecko fallback only")

col1, col2 = st.columns([3,1])

with col1:
    symbol_label = st.text_input("Symbol (display only)", value="BTC")
    if st.button("Fetch BTC data"):
        with st.spinner("Fetching data..."):
            try:
                df, source = fetch_btc_ohlcv_resilient(timeframe=timeframe, limit=limit, try_exchanges=None)
                st.success(f"Data source: {source}")
                # normalize columns: coinGecko returns lowercase timestamps for index -> ensure 'timestamp' col
                if "timestamp" in df.columns:
                    df = df.rename(columns={"timestamp": "open_time"})
                if "open_time" not in df.columns:
                    # try to detect time col
                    possible_time_cols = [c for c in df.columns if "time" in c.lower() or c.lower() == "timestamp"]
                    if possible_time_cols:
                        df = df.rename(columns={possible_time_cols[0]: "open_time"})
                df["open_time"] = pd.to_datetime(df["open_time"])
                df = df.sort_values("open_time").reset_index(drop=True)
                # Ensure numeric types
                for c in ["open","high","low","close","volume"]:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors="coerce")
                # Show table
                st.dataframe(df.tail(100))
                # Plot candlestick + RSI using Plotly
                try:
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=df["open_time"],
                        open=df["open"],
                        high=df["high"],
                        low=df["low"],
                        close=df["close"],
                        name="OHLC"
                    ))
                    # Compute RSI
                    df["rsi"] = compute_rsi(df["close"].astype(float))
                    rsi_fig = go.Figure()
                    rsi_fig.add_trace(go.Scatter(x=df["open_time"], y=df["rsi"], name="RSI"))
                    rsi_fig.update_layout(height=200, margin=dict(t=10,b=10,l=40,r=40))
                    fig.update_layout(title=f"BTC — {timeframe} — source: {source}", xaxis_rangeslider_visible=False, height=600)
                    st.plotly_chart(fig, use_container_width=True)
                    st.plotly_chart(rsi_fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Plotly chart failed: {e}")
                # CSV download
                csv_buf = io.StringIO()
                df.to_csv(csv_buf, index=False)
                csv_bytes = csv_buf.getvalue().encode()
                st.download_button("Download CSV", data=csv_bytes, file_name=f"BTC_{timeframe}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv")
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")

with col2:
    st.header("Notes")
    st.write(dedent("""
    - The app tries several exchanges (via ccxt) if `ccxt` is installed.
    - If exchanges block your IP, the app falls back to CoinGecko (resampled OHLC).
    - CoinGecko provides tick/prices which are resampled — good for indicators/backtesting but not exchange-exact candles.
    - If you plan to do live trading, ensure you use an exchange & location permitted by that exchange and do NOT bypass terms using VPN unless allowed.
    """))
    if st.button("Revoke example tokens (noop)"):
        st.info("No tokens stored in this demo.")