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
    # --- Williams %R ---
    df["WILLR"] = ta.momentum.WilliamsRIndicator(
        high=df["high"], low=df["low"], close=df["close"], lbp=14
    ).williams_r()
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
# RSI SCANNERS (Sidebar)
# ==============================


# ==============================
# RSI SCANNERS (Sidebar)
# ==============================
st.sidebar.subheader("🔥 RSI Scanners (All USDT Pairs)")
enable_scanner = st.sidebar.checkbox("Enable RSI Scanner", value=False)

# Initialize variables to avoid NameError when scanner is off
rsi_above, rsi_below = [], []
selected_from_scanner = None

if enable_scanner:
    rsi_tf = st.sidebar.radio("RSI Timeframe", list(TIMEFRAMES.keys()), index=2, horizontal=True)

    all_symbols = fetch_all_usdt_pairs()

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

    if rsi_above:
        st.sidebar.write(f"RSI > 70 ({rsi_tf})")
        df_rsi_above = pd.DataFrame(rsi_above).sort_values("RSI", ascending=False)
        st.sidebar.dataframe(df_rsi_above.style.background_gradient(cmap="Reds"))
        selected_from_scanner = st.sidebar.selectbox(
            "📈 Analyse Overbought Coin",
            options=["None"] + df_rsi_above["Symbol"].tolist(),
            index=0
        )

    if rsi_below and (not selected_from_scanner or selected_from_scanner == "None"):
        st.sidebar.write(f"RSI < 30 ({rsi_tf})")
        df_rsi_below = pd.DataFrame(rsi_below).sort_values("RSI", ascending=True)
        st.sidebar.dataframe(df_rsi_below.style.background_gradient(cmap="Greens"))
        selected_from_scanner = st.sidebar.selectbox(
            "📉 Analyse Oversold Coin",
            options=["None"] + df_rsi_below["Symbol"].tolist(),
            index=0
        )

# Final coin selection logic
if selected_from_scanner and selected_from_scanner != "None":
    selected_symbol = selected_from_scanner
# Final coin selection logic
if selected_from_scanner and selected_from_scanner != "None":
    selected_symbol = selected_from_scanner

# ==============================
# MAIN CHART AREA
# ==============================
if selected_symbol:
    chart_df = fetch_ohlcv(selected_symbol, TIMEFRAMES[timeframe], limit)
    chart_df = add_indicators(chart_df)

    st.subheader(f"📊 Candlestick + RSI + MACD + Williams %R for {selected_symbol} ({timeframe})")

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

    # ----------- RSI (2nd Panel)
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["RSI"],
        mode="lines", name="RSI", yaxis="y2"
    ))

    # ----------- MACD (3rd Panel)
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

    # ----------- Williams %R (4th Panel)
    fig.add_trace(go.Scatter(
        x=chart_df["time"], y=chart_df["WILLR"],
        mode="lines", name="Williams %R", yaxis="y4", line=dict(color="purple")
    ))

    # ----------- Layout (4 Equal Panels)
    fig.update_layout(
        height=1300,
        xaxis=dict(domain=[0, 1], rangeslider=dict(visible=False)),  # remove zoom bar
        yaxis=dict(title="Price", domain=[0.75, 1]),
        yaxis2=dict(title="RSI", domain=[0.5, 0.74], range=[0, 100]),
        yaxis3=dict(title="MACD", domain=[0.25, 0.49]),
        yaxis4=dict(title="Williams %R", domain=[0, 0.24], range=[-100, 0]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )


    # ----------- Crosshair spanning all subplots
    fig.update_layout(
        hovermode="x unified",
    )

    # RSI threshold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", yref="y2")
    fig.add_hline(y=30, line_dash="dash", line_color="green", yref="y2")

    # Williams %R thresholds
    fig.add_hline(y=-20, line_dash="dash", line_color="red", yref="y4")
    fig.add_hline(y=-80, line_dash="dash", line_color="green", yref="y4")


    # ----------- Signal Detection for Williams %R & RSI condition (15m only)
    willr_signals = []
    if timeframe == "15m":
        for i in range(1, len(chart_df)):
            if chart_df["WILLR"].iloc[i-1] > -20 and chart_df["WILLR"].iloc[i] <= -20:
                if chart_df["RSI"].iloc[i] > 69:
                    price_at_signal = chart_df["close"].iloc[i]
                    willr_signals.append((chart_df["time"].iloc[i], chart_df["WILLR"].iloc[i], price_at_signal))

    # Plot markers on Williams %R
    if willr_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in willr_signals],
            y=[s[1] for s in willr_signals],
            mode="markers+text",
            text=[f"{s[2]:.2f}" for s in willr_signals],
            textposition="top center",
            marker=dict(color="red", size=10, symbol="arrow-down"),
            name="WILLR Signal",
            yaxis="y4"
        ))


    # ----------- Signal Detection for RSI > 69, Price Down, and Williams %R touching -20 (15m only)
    willr_signals = []
    price_signals = []
    if timeframe == "15m":
        for i in range(1, len(chart_df)):
            # Condition: RSI > 69, Price moving down, and WILLR crosses/touches -20
            if chart_df["RSI"].iloc[i] > 69 and chart_df["close"].iloc[i] < chart_df["close"].iloc[i-1]:
                if chart_df["WILLR"].iloc[i-1] > -20 and chart_df["WILLR"].iloc[i] <= -20:
                    price_at_signal = chart_df["close"].iloc[i]
                    signal_time = chart_df["time"].iloc[i]
                    signal_willr = chart_df["WILLR"].iloc[i]
                    willr_signals.append((signal_time, signal_willr, price_at_signal))
                    price_signals.append((signal_time, price_at_signal))

    # Plot markers on Williams %R panel
    if willr_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in willr_signals],
            y=[s[1] for s in willr_signals],
            mode="markers+text",
            text=[f"{s[2]:.2f}" for s in willr_signals],
            textposition="top center",
            marker=dict(color="red", size=10, symbol="arrow-down"),
            name="WILLR Signal",
            yaxis="y4"
        ))

    # Plot markers on Price Candlestick panel
    if price_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in price_signals],
            y=[s[1] for s in price_signals],
            mode="markers+text",
            text=[f"{s[1]:.2f}" for s in price_signals],
            textposition="bottom center",
            marker=dict(color="red", size=12, symbol="arrow-down"),
            name="Price Signal",
            yaxis="y1"
        ))


    # ----------- Signal Detection: RSI in previous 4–10 candles >= 70, Price Down, Williams %R cross -20 (15m only)
    willr_signals = []
    price_signals = []
    if timeframe == "15m":
        for i in range(10, len(chart_df)):
            # Check RSI in the previous 4–10 candles (excluding current candle)
            rsi_window = chart_df["RSI"].iloc[i-10:i-4]
            if (rsi_window >= 70).any():
                # Price moving down
                if chart_df["close"].iloc[i] < chart_df["close"].iloc[i-1]:
                    # Williams %R crosses/touches -20
                    if chart_df["WILLR"].iloc[i-1] > -20 and chart_df["WILLR"].iloc[i] <= -20:
                        price_at_signal = chart_df["close"].iloc[i]
                        signal_time = chart_df["time"].iloc[i]
                        signal_willr = chart_df["WILLR"].iloc[i]
                        willr_signals.append((signal_time, signal_willr, price_at_signal))
                        price_signals.append((signal_time, price_at_signal))

    # Plot markers on Williams %R panel
    if willr_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in willr_signals],
            y=[s[1] for s in willr_signals],
            mode="markers+text",
            text=[f"{s[2]:.2f}" for s in willr_signals],
            textposition="top center",
            marker=dict(color="red", size=10, symbol="arrow-down"),
            name="WILLR Signal",
            yaxis="y4"
        ))

    # Plot markers on Price Candlestick panel
    if price_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in price_signals],
            y=[s[1] for s in price_signals],
            mode="markers+text",
            text=[f"{s[1]:.2f}" for s in price_signals],
            textposition="bottom center",
            marker=dict(color="red", size=12, symbol="arrow-down"),
            name="Price Signal",
            yaxis="y1"
        ))

    # ==============================
    # UNIFIED SIGNAL ENGINE (15m only) — relaxed buy rules
    # ==============================
    sell_price_signals, sell_willr_signals = [], []
    buy_price_signals, buy_willr_signals = [], []

    if timeframe == "15m":
        for i in range(12, len(chart_df)):
            # Helper windows / values
            close_now, close_prev = chart_df["close"].iloc[i], chart_df["close"].iloc[i-1]
            open_now = chart_df["open"].iloc[i]
            high_now, low_now = chart_df["high"].iloc[i], chart_df["low"].iloc[i]
            rsi_now, rsi_prev = chart_df["RSI"].iloc[i], chart_df["RSI"].iloc[i-1]
            rsi_recent = chart_df["RSI"].iloc[i-12:i]  # last 12 bars including current
            willr_prev, willr_now = chart_df["WILLR"].iloc[i-1], chart_df["WILLR"].iloc[i]
            willr_last3 = chart_df["WILLR"].iloc[i-3:i]  # last 3 bars, excl current end

            # --- SELL --- (same as before)
            sell_rsi_ok = (rsi_now > 70) or ((chart_df["RSI"].iloc[i-10:i-4] >= 70).any())
            sell_price_down = close_now < close_prev
            sell_willr_cross_dn = (willr_prev > -20) and (willr_now <= -20)

            if sell_rsi_ok and sell_price_down and sell_willr_cross_dn:
                # arrow above candle on price chart
                price_at_signal = high_now * 1.001  # just above the candle high
                sell_price_signals.append((chart_df["time"].iloc[i], price_at_signal))
                sell_willr_signals.append((chart_df["time"].iloc[i], willr_now, close_now))

            # --- BUY --- (relaxed to fire in realistic oversold reversals)
            # RSI oversold or recently oversold or crossing back above 30 now
            buy_rsi_ok = (
                (rsi_now < 30) or
                (rsi_prev < 30 and rsi_now >= 30) or
                (rsi_recent.min() <= 30)
            )
            # Price moving up (bullish body OR close above previous close)
            buy_price_up = (close_now > open_now) or (close_now >= close_prev)
            # W%R crosses up -80 strictly OR emerged from <=-85 within the last 3 bars and now >= -80
            buy_willr_cross_up_strict = (willr_prev <= -80) and (willr_now > -80)
            buy_willr_cross_up_window = (willr_last3.min() <= -85) and (willr_now >= -80)
            buy_willr_ok = buy_willr_cross_up_strict or buy_willr_cross_up_window

            if buy_rsi_ok and buy_price_up and buy_willr_ok:
                # arrow below candle on price chart
                price_at_signal = low_now * 0.999  # just below the candle low
                buy_price_signals.append((chart_df["time"].iloc[i], price_at_signal))
                buy_willr_signals.append((chart_df["time"].iloc[i], willr_now, close_now))

    # ---- Plot SELL markers ----
    if sell_willr_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in sell_willr_signals],
            y=[s[1] for s in sell_willr_signals],
            mode="markers+text",
            text=[f"{s[2]:.2f}" for s in sell_willr_signals],
            textposition="top center",
            marker=dict(color="red", size=10, symbol="arrow-down"),
            name="W%R Sell",
            yaxis="y4"
        ))
    if sell_price_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in sell_price_signals],
            y=[s[1] for s in sell_price_signals],
            mode="markers",
            marker=dict(color="red", size=12, symbol="arrow-down"),
            name="Sell Signal",
            yaxis="y1"
        ))

    # ---- Plot BUY markers ----
    if buy_willr_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in buy_willr_signals],
            y=[s[1] for s in buy_willr_signals],
            mode="markers+text",
            text=[f"{s[2]:.2f}" for s in buy_willr_signals],
            textposition="bottom center",
            marker=dict(color="green", size=10, symbol="arrow-up"),
            name="W%R Buy",
            yaxis="y4"
        ))
    if buy_price_signals:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in buy_price_signals],
            y=[s[1] for s in buy_price_signals],
            mode="markers",
            marker=dict(color="green", size=12, symbol="arrow-up"),
            name="Buy Signal",
            yaxis="y1"
        ))

    st.plotly_chart(fig, use_container_width=True)