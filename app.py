import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import ta

# ==============================
# CONFIG
# ==============================
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_TICKER = "https://api.binance.com/api/v3/ticker/24hr"

WATCHLIST = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
             "ADAUSDT", "DOGEUSDT", "MATICUSDT", "LTCUSDT", "DOTUSDT"]

TIMEFRAMES = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

# ==============================
# STREAMLIT UI
# ==============================
st.set_page_config(page_title="Binance RSI & MACD Scanner", layout="wide")
st.title("📊 Binance RSI + MACD Scanner")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

# Timeframe selector (main chart)
timeframe = st.radio("⏱️ Select Timeframe (Main Chart)", list(TIMEFRAMES.keys()), index=2, horizontal=True)

# Sidebar
st.sidebar.header("⚙️ Settings")
limit = st.sidebar.slider("Candles to fetch", min_value=50, max_value=500, value=200)

# ==============================
# FETCH OHLCV DATA
# ==============================
@st.cache_data(ttl=300)
def fetch_ohlcv(symbol: str, interval: str, limit: int):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(BINANCE_KLINES, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        return df
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

# ==============================
# FETCH MOST TRADED COINS
# ==============================
@st.cache_data(ttl=300)
def fetch_most_traded(n=10):
    try:
        r = requests.get(BINANCE_TICKER, timeout=10)
        r.raise_for_status()
        data = pd.DataFrame(r.json())
        data["count"] = pd.to_numeric(data["count"], errors="coerce")
        return data.sort_values("count", ascending=False).head(n)
    except Exception as e:
        st.error(f"Error fetching most-traded coins: {e}")
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

def get_latest_rsi(symbol, interval="15m", limit=200):
    df = fetch_ohlcv(symbol, interval, limit)
    if df.empty:
        return None
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    return round(df["RSI"].iloc[-1], 2)

# ==============================
# SIDEBAR COIN SELECTOR
# ==============================
st.sidebar.subheader("📌 Select Coin")
coin_source = st.sidebar.radio("Choose list", ["Watchlist", "Most Traded"])

if coin_source == "Watchlist":
    selected_symbol = st.sidebar.radio("Coins", WATCHLIST, index=0)
else:
    most_traded = fetch_most_traded(10)
    if not most_traded.empty:
        traded_coins = most_traded["symbol"].tolist()
        selected_symbol = st.sidebar.radio("Most-Traded Coins", traded_coins, index=0)
        st.sidebar.dataframe(most_traded[["symbol", "lastPrice", "priceChangePercent", "count"]])
    else:
        selected_symbol = WATCHLIST[0]

# ==============================
# FETCH ALL BINANCE USDT PAIRS
# ==============================
@st.cache_data(ttl=600)
def fetch_all_usdt_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Only USDT pairs, trading status must be TRADING
        symbols = [s["symbol"] for s in data["symbols"] if s["status"] == "TRADING" and s["symbol"].endswith("USDT")]
        return symbols
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return WATCHLIST  # fallback

from streamlit_autorefresh import st_autorefresh

# Auto-refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="rsirefresh")

# ==============================
# RSI SCANNERS (Sidebar)
# ==============================
st.sidebar.subheader("🔥 RSI Scanners (All USDT Pairs)")

# Manual refresh button
if st.sidebar.button("🔄 Refresh RSI Scanner"):
    st.cache_data.clear()

# Force 5m timeframe
rsi_tf = "5m"
st.sidebar.write("Timeframe: ⏱️ 5m (auto-refresh every 30s)")

all_symbols = fetch_all_usdt_pairs()

rsi_above = []
rsi_below = []

# Limit number of coins to scan (avoid timeout)
MAX_COINS = 100
symbols_to_scan = all_symbols[:MAX_COINS]

progress_bar = st.sidebar.progress(0)
for i, sym in enumerate(symbols_to_scan):
    rsi_val = get_latest_rsi(sym, rsi_tf, limit)
    if rsi_val:
        if rsi_val > 70:
            rsi_above.append({"Symbol": sym, "RSI": rsi_val})
        elif rsi_val < 30:
            rsi_below.append({"Symbol": sym, "RSI": rsi_val})
    progress_bar.progress((i + 1) / len(symbols_to_scan))
progress_bar.empty()

selected_from_scanner = None  # override coin if picked

if rsi_above:
    st.sidebar.write(f"RSI > 70 ({rsi_tf})")
    df_rsi_above = pd.DataFrame(rsi_above).sort_values("RSI", ascending=False)
    st.sidebar.dataframe(df_rsi_above.style.background_gradient(cmap="Reds"))
    selected_from_scanner = st.sidebar.selectbox(
        "📈 Analyse Overbought Coin",
        options=["None"] + df_rsi_above["Symbol"].tolist(),
        index=0
    )

if rsi_below:
    st.sidebar.write(f"RSI < 30 ({rsi_tf})")
    df_rsi_below = pd.DataFrame(rsi_below).sort_values("RSI", ascending=True)
    st.sidebar.dataframe(df_rsi_below.style.background_gradient(cmap="Greens"))
    if not selected_from_scanner or selected_from_scanner == "None":
        selected_from_scanner = st.sidebar.selectbox(
            "📉 Analyse Oversold Coin",
            options=["None"] + df_rsi_below["Symbol"].tolist(),
            index=0
        )

# Final coin selection logic
if selected_from_scanner and selected_from_scanner != "None":
    selected_symbol = selected_from_scanner



# ==============================
# MAIN CHART AREA
# ==============================
if selected_symbol:
    chart_df = fetch_ohlcv(selected_symbol, TIMEFRAMES[timeframe], limit)
    chart_df = add_indicators(chart_df)

    st.subheader(f"📊 Candlestick + RSI + MACD for {selected_symbol} ({timeframe})")

    latest_price = chart_df["close"].iloc[-1]

    fig = go.Figure()

    # ----------- Price (Top Panel)
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

    # ----------- RSI (Middle Panel)
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["RSI"],
        mode="lines", name="RSI", yaxis="y2"
    ))

    # ----------- MACD (Bottom Panel)
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

    # ----------- Layout (Equal Panels)
    fig.update_layout(
        height=1000,
        xaxis=dict(domain=[0, 1], rangeslider=dict(visible=False)),  # remove zoom bar
        yaxis=dict(title="Price", domain=[0.66, 1]),
        yaxis2=dict(title="RSI", domain=[0.33, 0.65], range=[0, 100]),
        yaxis3=dict(title="MACD", domain=[0, 0.32]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # RSI threshold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", yref="y2")
    fig.add_hline(y=30, line_dash="dash", line_color="green", yref="y2")

    st.plotly_chart(fig, use_container_width=True)
