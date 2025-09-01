import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import ta
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# ==============================
# CONFIG
# ==============================
st.set_page_config(page_title="CoinPaprika RSI & MACD Scanner", layout="wide")
st.title("📊 CoinPaprika RSI + MACD Scanner (Public API)")

# Auto-refresh every 30s
st_autorefresh(interval=30 * 1000, key="rsirefresh")

# Supported coins (you can extend this list)
COINS = {
    "BTCUSDT": "btc-bitcoin",
    "ETHUSDT": "eth-ethereum",
    "BNBUSDT": "bnb-binance-coin",
    "XRPUSDT": "xrp-xrp",
    "SOLUSDT": "sol-solana",
    "ADAUSDT": "ada-cardano",
    "DOGEUSDT": "doge-dogecoin",
    "MATICUSDT": "matic-polygon",
    "LTCUSDT": "ltc-litecoin",
    "DOTUSDT": "dot-polkadot",
}

# Timeframes mapping (CoinPaprika only supports fixed intervals)
TIMEFRAMES = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d"
}

# ==============================
# FETCH OHLCV DATA FROM COINPAPRIKA
# ==============================
from datetime import datetime, timedelta

@st.cache_data(ttl=300)
def fetch_ohlcv(symbol: str, tf: str = "5m", limit: int = 200):
    coin_id = COINS.get(symbol, "btc-bitcoin")  # fallback BTC
    end = datetime.utcnow()
    start = end - timedelta(days=7)  # up to 7 days history
    url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}/historical"
    try:
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": tf
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["timestamp"])
        df.rename(columns={"price": "close"}, inplace=True)
        df["close"] = pd.to_numeric(df["close"])
        df["open"] = df["close"].shift(1).fillna(df["close"])
        df["high"] = df["close"].rolling(3).max().fillna(df["close"])
        df["low"] = df["close"].rolling(3).min().fillna(df["close"])
        df["volume"] = df.get("volume", 0)
        return df.tail(limit)
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

# ==============================
# INDICATORS
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
timeframe = st.sidebar.radio("Chart Timeframe", list(TIMEFRAMES.keys()), index=0, horizontal=True)

# ==============================
# RSI SCANNER
# ==============================
st.sidebar.subheader("🔥 RSI Scanners (CoinPaprika)")
st.sidebar.write("Timeframe: ⏱️ 5m (auto-refresh every 30s)")

rsi_above = []
rsi_below = []

for sym in COINS.keys():
    rsi_val = get_latest_rsi(sym, "5m", limit)
    if rsi_val:
        if rsi_val > 70:
            rsi_above.append({"Symbol": sym, "RSI": rsi_val})
        elif rsi_val < 30:
            rsi_below.append({"Symbol": sym, "RSI": rsi_val})

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
chart_df = fetch_ohlcv(selected_symbol, timeframe, limit)
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
