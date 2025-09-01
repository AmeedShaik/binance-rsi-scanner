import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import ta
from streamlit_autorefresh import st_autorefresh

# ==============================
# CONFIG
# ==============================
st.set_page_config(page_title="Binance RSI & MACD Scanner", layout="wide")
st.title("📊 Binance RSI + MACD Scanner (Public REST API)")

# Auto-refresh every 30s
st_autorefresh(interval=30 * 1000, key="rsirefresh")

BINANCE_BASE = "https://api.binance.com/api/v3"
BINANCE_KLINES = f"{BINANCE_BASE}/klines"
BINANCE_EXCHANGE_INFO = f"{BINANCE_BASE}/exchangeInfo"

TIMEFRAMES = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

# ==============================
# FETCH ALL USDT PAIRS
# ==============================
@st.cache_data(ttl=600)
def fetch_all_usdt_pairs():
    try:
        r = requests.get(BINANCE_EXCHANGE_INFO, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [s["symbol"] for s in data["symbols"]
                   if s["status"] == "TRADING" and s["symbol"].endswith("USDT")]
        return symbols
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return ["BTCUSDT", "ETHUSDT"]

# ==============================
# FETCH OHLCV DATA
# ==============================
@st.cache_data(ttl=300)
def fetch_ohlcv(symbol: str, interval: str = "5m", limit: int = 200):
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(BINANCE_KLINES, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","qav","trades","taker_base","taker_quote","ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])
        return df
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

# ==============================
# CALCULATE INDICATORS
# ==============================
def add_indicators(df: pd.DataFrame):
    if df.empty:
        return df
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()
    return df

def get_latest_rsi(symbol, interval="5m", limit=200):
    df = fetch_ohlcv(symbol, interval, limit)
    if df.empty:
        return None
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    return round(df["RSI"].iloc[-1], 2)

# ==============================
# SIDEBAR SETTINGS
# ==============================
st.sidebar.header("⚙️ Settings")
limit = st.sidebar.slider("Candles to fetch", min_value=50, max_value=500, value=200)
timeframe = st.sidebar.radio("Chart Timeframe", list(TIMEFRAMES.keys()), index=2, horizontal=True)

# ==============================
# RSI SCANNER (All USDT Pairs, 5m TF, Auto-refresh 30s)
# ==============================
st.sidebar.subheader("🔥 RSI Scanners (All USDT Pairs)")
st.sidebar.write("Timeframe: ⏱️ 5m (auto-refresh every 30s)")

all_symbols = fetch_all_usdt_pairs()

rsi_above = []
rsi_below = []

MAX_COINS = 100  # limit to avoid timeouts
symbols_to_scan = all_symbols[:MAX_COINS]

progress_bar = st.sidebar.progress(0)
for i, sym in enumerate(symbols_to_scan):
    rsi_val = get_latest_rsi(sym, "5m", limit)
    if rsi_val:
        if rsi_val > 70:
            rsi_above.append({"Symbol": sym, "RSI": rsi_val})
        elif rsi_val < 30:
            rsi_below.append({"Symbol": sym, "RSI": rsi_val})
    progress_bar.progress((i + 1) / len(symbols_to_scan))
progress_bar.empty()

selected_from_scanner = None

if rsi_above:
    st.sidebar.write("RSI > 70 (Overbought)")
    df_rsi_above = pd.DataFrame(rsi_above).sort_values("RSI", ascending=False)
    st.sidebar.dataframe(df_rsi_above.style.background_gradient(cmap="Reds"))
    selected_from_scanner = st.sidebar.selectbox(
        "📈 Analyse Overbought Coin",
        options=["None"] + df_rsi_above["Symbol"].tolist(),
        index=0
    )

if rsi_below:
    st.sidebar.write("RSI < 30 (Oversold)")
    df_rsi_below = pd.DataFrame(rsi_below).sort_values("RSI", ascending=True)
    st.sidebar.dataframe(df_rsi_below.style.background_gradient(cmap="Greens"))
    if not selected_from_scanner or selected_from_scanner == "None":
        selected_from_scanner = st.sidebar.selectbox(
            "📉 Analyse Oversold Coin",
            options=["None"] + df_rsi_below["Symbol"].tolist(),
            index=0
        )

# Default symbol if none selected
if not selected_from_scanner or selected_from_scanner == "None":
    selected_symbol = "BTCUSDT"
else:
    selected_symbol = selected_from_scanner

# ==============================
# MAIN CHART AREA
# ==============================
chart_df = fetch_ohlcv(selected_symbol, TIMEFRAMES[timeframe], limit)
chart_df = add_indicators(chart_df)

if not chart_df.empty:
    latest_price = chart_df["close"].iloc[-1]

    st.subheader(f"📊 {selected_symbol} ({timeframe}) Candlestick + RSI + MACD")

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=chart_df["time"],
        open=chart_df["open"],
        high=chart_df["high"],
        low=chart_df["low"],
        close=chart_df["close"],
        name="Price",
        yaxis="y1"
    ))

    # Price line
    fig.add_hline(y=latest_price, line_dash="solid", line_color="orange",
                  annotation_text=f"Price: {latest_price}", annotation_position="top right", yref="y1")

    # RSI
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["RSI"],
        mode="lines", name="RSI", yaxis="y2"
    ))

    # MACD
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["MACD"],
        mode="lines", name="MACD", yaxis="y3", line=dict(color="blue")
    ))
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["MACD_Signal"],
        mode="lines", name="Signal", yaxis="y3", line=dict(color="red")
    ))
    fig.add_trace(go.Bar(
        x=chart_df["time"], y=chart_df["MACD_Hist"],
        name="Histogram", yaxis="y3", marker_color="gray"
    ))

    # Layout
    fig.update_layout(
        height=1000,
        xaxis=dict(domain=[0, 1], rangeslider=dict(visible=False)),
        yaxis=dict(title="Price", domain=[0.66, 1]),
        yaxis2=dict(title="RSI", domain=[0.33, 0.65], range=[0, 100]),
        yaxis3=dict(title="MACD", domain=[0, 0.32]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # RSI thresholds
    fig.add_hline(y=70, line_dash="dash", line_color="red", yref="y2")
    fig.add_hline(y=30, line_dash="dash", line_color="green", yref="y2")

    st.plotly_chart(fig, use_container_width=True)
