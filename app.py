
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

from datetime import datetime

# =========================================
# TRADING STAR GOLD LIVE RADAR V2.0
# =========================================

st.set_page_config(
    page_title="Trading Star Gold Live Radar",
    page_icon="📡",
    layout="wide"
)

st.title("📡 TRADING STAR")
st.subheader("GOLD LIVE WAVE RADAR")
st.caption("Live data prototype | Multi-Timeframe Research Engine")

# =========================================
# DATA DOWNLOAD
# =========================================

@st.cache_data(ttl=45, show_spinner=False)
def download_gold_data():

    ticker = yf.Ticker("GC=F")

    df = ticker.history(
        period="5d",
        interval="15m",
        auto_adjust=False
    )

    if df is None or df.empty:
        raise ValueError("Yahoo Finance returned no Gold data.")

    df = df.reset_index()

    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    elif "Date" not in df.columns:
        raise ValueError("Date column not available.")

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    required = ["Date", "open", "high", "low", "close"]

    if not all(c in df.columns for c in required):
        raise ValueError("Required OHLC columns missing.")

    df["Date"] = pd.to_datetime(df["Date"])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" not in df.columns:
        df["volume"] = 0

    df["volume"] = pd.to_numeric(
        df["volume"], errors="coerce"
    ).fillna(0)

    df = df.dropna(subset=required)
    df = df.sort_values("Date")
    df = df.drop_duplicates("Date")
    df = df.set_index("Date")

    # Exclude incomplete 15-minute candle
    if df.index.tz is not None:
        now = pd.Timestamp.now(tz=df.index.tz)
    else:
        now = pd.Timestamp.now()

    df = df[
        df.index + pd.Timedelta(minutes=15) <= now
    ]

    if len(df) < 60:
        raise ValueError(
            "Not enough completed Gold candles. "
            "Try again when market data is available."
        )

    return df


# =========================================
# TIMEFRAME CONVERSION
# =========================================

def make_timeframe(df, rule):

    if rule == "15min":
        result = df.copy()
    else:
        result = df.resample(
            rule,
            label="right",
            closed="right"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        })

    result = result.dropna(
        subset=["open", "high", "low", "close"]
    )

    # Remove current incomplete timeframe candle
    if result.index.tz is not None:
        now = pd.Timestamp.now(tz=result.index.tz)
    else:
        now = pd.Timestamp.now()

    minutes = {
        "15min": 15,
        "30min": 30,
        "1h": 60
    }[rule]

    result = result[
        result.index + pd.Timedelta(minutes=minutes) <= now
    ]

    return result


# =========================================
# INDICATORS
# =========================================

def add_indicators(df):

    df = df.copy()

    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14,
        min_periods=14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14,
        min_periods=14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    df["RSI"] = df["RSI"].fillna(50)

    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9, adjust=False
    ).mean()

    df["MACD_HIST"] = macd - signal

    return df


# =========================================
# CONFIRMED SWING DETECTION
# =========================================

def detect_swings(df, left=3, right=3):

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()

    points = []

    for i in range(left, len(df) - right):

        high_window = highs[i-left:i+right+1]
        low_window = lows[i-left:i+right+1]

        if (
            highs[i] == np.max(high_window)
            and np.sum(high_window == highs[i]) == 1
        ):
            points.append({
                "index": i,
                "type": "HIGH",
                "price": float(highs[i])
            })

        if (
            lows[i] == np.min(low_window)
            and np.sum(low_window == lows[i]) == 1
        ):
            points.append({
                "index": i,
                "type": "LOW",
                "price": float(lows[i])
            })

    points.sort(key=lambda p: p["index"])

    swings = []

    for p in points:

        if not swings:
            swings.append(p)
            continue

        previous = swings[-1]

        if p["type"] != previous["type"]:
            swings.append(p)

        elif p["type"] == "HIGH":
            if p["price"] > previous["price"]:
                swings[-1] = p

        elif p["type"] == "LOW":
            if p["price"] < previous["price"]:
                swings[-1] = p

    previous_high = None
    previous_low = None

    for p in swings:

        if p["type"] == "HIGH":

            if previous_high is None:
                p["structure"] = "INITIAL HIGH"
            elif p["price"] > previous_high:
                p["structure"] = "HH"
            else:
                p["structure"] = "LH"

            previous_high = p["price"]

        else:

            if previous_low is None:
                p["structure"] = "INITIAL LOW"
            elif p["price"] > previous_low:
                p["structure"] = "HL"
            else:
                p["structure"] = "LL"

            previous_low = p["price"]

    return swings


# =========================================
# DIRECTIONAL ANALYSIS
# =========================================

def analyze_timeframe(df):

    df = add_indicators(df)

    if len(df) < 55:
        raise ValueError("Not enough candles for analysis.")

    last = df.iloc[-1]

    score = 0

    # Trend
    if last["EMA20"] > last["EMA50"]:
        score += 2
    elif last["EMA20"] < last["EMA50"]:
        score -= 2

    # RSI momentum
    if last["RSI"] > 55:
        score += 1
    elif last["RSI"] < 45:
        score -= 1

    # MACD momentum
    if last["MACD_HIST"] > 0:
        score += 1
    elif last["MACD_HIST"] < 0:
        score -= 1

    # Confirmed swing structure
    swings = detect_swings(df)

    recent = [
        p["structure"] for p in swings[-6:]
    ]

    if "HH" in recent and "HL" in recent:
        score += 2
        structure = "BULLISH STRUCTURE"

    elif "LH" in recent and "LL" in recent:
        score -= 2
        structure = "BEARISH STRUCTURE"

    else:
        structure = "MIXED STRUCTURE"

    alignment = round((score / 6) * 100)

    if alignment >= 30:
        direction = "BULLISH"

    elif alignment <= -30:
        direction = "BEARISH"

    else:
        direction = "NEUTRAL"

    if abs(alignment) >= 65:
        strength = "STRONG"

    elif abs(alignment) >= 30:
        strength = "MODERATE"

    else:
        strength = "WEAK"

    return {
        "data": df,
        "swings": swings,
        "direction": direction,
        "alignment": alignment,
        "strength": strength,
        "structure": structure,
        "rsi": round(float(last["RSI"]), 2),
        "ema20": float(last["EMA20"]),
        "ema50": float(last["EMA50"]),
        "price": float(last["close"]),
        "last_time": df.index[-1]
    }


# =========================================
# CHART
# =========================================

def draw_chart(result, title):

    df = result["data"].tail(120)
    swings = result["swings"]

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Gold"
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA20"],
        mode="lines",
        name="EMA 20"
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA50"],
        mode="lines",
        name="EMA 50"
    ))

    visible_swings = [
        p for p in swings
        if p["index"] >= len(result["data"]) - 120
    ]

    if visible_swings:

        fig.add_trace(go.Scatter(
            x=[
                result["data"].index[p["index"]]
                for p in visible_swings
            ],
            y=[p["price"] for p in visible_swings],
            mode="lines+markers+text",
            text=[p["structure"] for p in visible_swings],
            textposition="top center",
            name="Confirmed Swings"
        ))

    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=450,
        xaxis_rangeslider_visible=False
    )

    return fig


# =========================================
# LIVE RADAR
# =========================================

@st.fragment(run_every="60s")
def live_radar():

    st.caption(
        "Data source: Yahoo Finance | GC=F Gold Futures"
    )

    try:

        base = download_gold_data()

        data_15 = make_timeframe(base, "15min")
        data_30 = make_timeframe(base, "30min")
        data_60 = make_timeframe(base, "1h")

        results = {
            "15M": analyze_timeframe(data_15),
            "30M": analyze_timeframe(data_30),
            "1H": analyze_timeframe(data_60)
        }

        # OVERALL RADAR
        scores = [
            results[tf]["alignment"]
            for tf in ["15M", "30M", "1H"]
        ]

        overall = round(sum(scores) / len(scores))

        directions = [
            results[tf]["direction"]
            for tf in ["15M", "30M", "1H"]
        ]

        if all(d == "BULLISH" for d in directions):
            overall_direction = "BULLISH"

        elif all(d == "BEARISH" for d in directions):
            overall_direction = "BEARISH"

        else:
            overall_direction = "MIXED / NEUTRAL"

        st.success(
            "Gold market data loaded successfully."
        )

        latest = results["15M"]["price"]

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Gold Futures Price",
            f"${latest:,.2f}"
        )

        c2.metric(
            "Overall Direction",
            overall_direction
        )

        c3.metric(
            "Directional Alignment",
            f"{overall:+d} / 100"
        )

        st.caption(
            "Latest completed 15-minute candle: "
            + str(results["15M"]["last_time"])
        )

        # ALERTS
        st.divider()
        st.subheader("Market Radar Alerts")

        if (
            overall_direction == "BULLISH"
            and overall >= 50
        ):
            st.success(
                "BULLISH ALIGNMENT WATCH: "
                "1H, 30M and 15M are aligned bullish."
            )

        elif (
            overall_direction == "BEARISH"
            and overall <= -50
        ):
            st.warning(
                "BEARISH ALIGNMENT WATCH: "
                "1H, 30M and 15M are aligned bearish."
            )

        else:
            st.info(
                "NO FULL ALIGNMENT: "
                "Timeframes are mixed. Wait for confirmation."
            )

        st.caption(
            "Alerts are research observations, not entry signals."
        )

        # TIMEFRAME SUMMARY
        st.divider()
        st.subheader("Multi-Timeframe Intelligence")

        summary = []

        for tf in ["1H", "30M", "15M"]:

            r = results[tf]

            summary.append({
                "Timeframe": tf,
                "Direction": r["direction"],
                "Alignment Score": r["alignment"],
                "Strength": r["strength"],
                "Structure": r["structure"],
                "RSI": r["rsi"],
                "Price": round(r["price"], 2)
            })

        st.table(pd.DataFrame(summary))

        # CHARTS
        st.divider()
        st.subheader("Live Gold Wave Charts")

        for tf in ["1H", "30M", "15M"]:

            r = results[tf]

            st.markdown(f"### {tf} Wave Analysis")

            st.write(
                f"Direction: {r['direction']} | "
                f"Strength: {r['strength']} | "
                f"Structure: {r['structure']}"
            )

            st.plotly_chart(
                draw_chart(r, f"Gold {tf}"),
                use_container_width=True
            )

        st.caption(
            "Radar refreshes every 60 seconds while this app session is active."
        )

    except Exception as e:

        st.error(
            f"Live Gold Data Error: {e}"
        )

        st.info(
            "Yahoo Finance data may be unavailable, "
            "delayed or temporarily rate-limited. "
            "Try refreshing later."
        )


live_radar()

st.divider()

st.caption(
    "TRADING STAR | GOLD LIVE WAVE RADAR | V2.0"
)
