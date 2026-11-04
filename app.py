
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Trading Star Market Radar",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Trading Star Market Radar")
st.caption("Historical Wave Intelligence | Research V1.3")
st.divider()


def normalize_columns(df):
    df.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in df.columns
    ]

    aliases = {
        "date": ["date", "datetime", "timestamp", "time"],
        "open": ["open", "o"],
        "high": ["high", "h"],
        "low": ["low", "l"],
        "close": ["close", "c", "adj_close"],
        "volume": ["volume", "vol", "tick_volume"]
    }

    rename = {}
    for standard, names in aliases.items():
        for name in names:
            if name in df.columns:
                rename[name] = standard
                break

    df = df.rename(columns=rename)

    required = ["date", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))

    if "volume" not in df.columns:
        df["volume"] = 0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=required)
    df = df.sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.reset_index(drop=True)

    if len(df) < 20:
        raise ValueError("At least 20 valid candles are required.")

    invalid = (
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    )

    if invalid.any():
        raise ValueError("Invalid OHLC candle data detected.")

    return df


def calculate_atr(df, period=14):
    prev = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(period, min_periods=period).mean()


def detect_swings(df, left=3, right=3):
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    candidates = []

    for i in range(left, len(df) - right):
        hw = highs[i-left:i+right+1]
        lw = lows[i-left:i+right+1]

        if highs[i] == np.max(hw) and np.sum(hw == highs[i]) == 1:
            candidates.append({
                "index": i,
                "type": "HIGH",
                "price": float(highs[i])
            })

        if lows[i] == np.min(lw) and np.sum(lw == lows[i]) == 1:
            candidates.append({
                "index": i,
                "type": "LOW",
                "price": float(lows[i])
            })

    candidates.sort(key=lambda x: x["index"])
    swings = []

    for p in candidates:
        if not swings:
            swings.append(p)
            continue

        prev = swings[-1]

        if p["type"] != prev["type"]:
            swings.append(p)
        elif p["type"] == "HIGH" and p["price"] > prev["price"]:
            swings[-1] = p
        elif p["type"] == "LOW" and p["price"] < prev["price"]:
            swings[-1] = p

    return swings


def classify_swings(swings):
    prev_high = None
    prev_low = None

    for p in swings:
        if p["type"] == "HIGH":
            if prev_high is None:
                p["structure"] = "INITIAL HIGH"
            elif p["price"] > prev_high:
                p["structure"] = "HH"
            else:
                p["structure"] = "LH"
            prev_high = p["price"]
        else:
            if prev_low is None:
                p["structure"] = "INITIAL LOW"
            elif p["price"] > prev_low:
                p["structure"] = "HL"
            else:
                p["structure"] = "LL"
            prev_low = p["price"]

    return swings


# SIDEBAR
st.sidebar.header("Market Settings")

market = st.sidebar.selectbox(
    "Select Market",
    ["XAUUSD", "NIFTY 50", "BANK NIFTY", "NSE STOCK", "FOREX"]
)

timeframe = st.sidebar.selectbox(
    "Select Timeframe",
    ["1H", "30M", "15M"]
)

uploaded_file = st.file_uploader(
    "Upload Historical OHLCV CSV",
    type=["csv"]
)

if uploaded_file is None:
    st.info("Upload a CSV file to begin historical wave analysis.")
    st.markdown("Required columns: Date, Open, High, Low, Close, Volume")
    st.code(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-01-01,100,105,98,103,15000\n"
        "2026-01-02,103,108,101,106,18000"
    )

else:
    try:
        data = pd.read_csv(uploaded_file)
        data = normalize_columns(data)
        data["ATR"] = calculate_atr(data)

        st.success("Historical data loaded and validated.")

        st.subheader("Market Overview")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Market", market)
        c2.metric("Timeframe", timeframe)
        c3.metric("Total Candles", len(data))
        c4.metric("Latest Close", f"{data['close'].iloc[-1]:.4f}")

        # PRICE CHART
        st.subheader("Historical Price Chart")

        price_fig = go.Figure()
        price_fig.add_trace(go.Candlestick(
            x=data["date"],
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            name="Price"
        ))

        price_fig.update_layout(
            template="plotly_dark",
            height=480,
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(price_fig, use_container_width=True)

        # WAVE ANALYSIS
        st.divider()
        st.subheader("Advanced Wave Structure Intelligence")

        swings = classify_swings(detect_swings(data))

        if len(swings) >= 2:
            wave_rows = []

            for j in range(1, len(swings)):
                a = swings[j - 1]
                b = swings[j]

                diff = b["price"] - a["price"]
                duration = b["index"] - a["index"]
                atr = data["ATR"].iloc[b["index"]]

                atr_multiple = (
                    abs(diff) / atr
                    if pd.notna(atr) and atr > 0
                    else np.nan
                )

                wave_rows.append({
                    "Wave": j,
                    "Direction": "BULLISH" if diff > 0 else "BEARISH",
                    "Structure": a["structure"] + " → " + b["structure"],
                    "Start Price": round(a["price"], 5),
                    "End Price": round(b["price"], 5),
                    "Movement": round(abs(diff), 5),
                    "Movement %": round(abs(diff) / a["price"] * 100, 3),
                    "Duration": duration,
                    "Velocity": round(abs(diff) / duration, 5),
                    "ATR Multiple": (
                        round(atr_multiple, 2)
                        if pd.notna(atr_multiple)
                        else None
                    )
                })

            waves = pd.DataFrame(wave_rows)

            bullish = int((waves["Direction"] == "BULLISH").sum())
            bearish = int((waves["Direction"] == "BEARISH").sum())

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Waves", len(waves))
            m2.metric("Bullish Waves", bullish)
            m3.metric("Bearish Waves", bearish)

            # STATIC TABLES - avoids interactive DataFrame component
            st.subheader("Swing Structure")

            structure_data = pd.DataFrame([
                {
                    "Time": data["date"].iloc[p["index"]],
                    "Swing Type": p["type"],
                    "Price": round(p["price"], 5),
                    "Classification": p["structure"]
                }
                for p in swings
            ])

            st.table(structure_data.tail(30))

            st.subheader("Wave Performance Table")
            st.table(waves.tail(30))

            # ECG WAVE MONITOR
            st.subheader("Market ECG Wave Monitor")

            wave_fig = go.Figure()
            wave_fig.add_trace(go.Scatter(
                x=[data["date"].iloc[p["index"]] for p in swings],
                y=[p["price"] for p in swings],
                mode="lines+markers+text",
                text=[p["structure"] for p in swings],
                textposition="top center",
                line=dict(color="#00E5A8", width=2),
                marker=dict(size=8),
                name="Confirmed Swings"
            ))

            wave_fig.update_layout(
                template="plotly_dark",
                height=430,
                xaxis_title="Date",
                yaxis_title="Price"
            )

            st.plotly_chart(wave_fig, use_container_width=True)

            # STRUCTURE OBSERVATION
            st.subheader("Market Structure Observation")

            recent = [p["structure"] for p in swings[-6:]]

            if "HH" in recent and "HL" in recent:
                st.success("Higher High and Higher Low structures detected. Bullish structure is present in recent confirmed swings.")
            elif "LH" in recent and "LL" in recent:
                st.warning("Lower High and Lower Low structures detected. Bearish structure is present in recent confirmed swings.")
            else:
                st.info("Mixed or developing structure. Wait for additional confirmed swings.")

            st.caption(
                "Historical structure observation only. "
                "Not a trading signal or a forecast."
            )

        else:
            st.warning("Insufficient confirmed swings. Upload more historical candles.")

        with st.expander("View Uploaded Historical Data"):
            st.table(data.tail(20))

    except Exception as e:
        st.error(f"Market Radar Error: {e}")
        st.info("Please check the CSV columns and data format.")

st.divider()
st.caption("TRADING STAR | MARKET RADAR | RESEARCH V1.3")
