
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# -----------------------------------------
# TRADING STAR MARKET RADAR
# VERSION 1.2
# -----------------------------------------

st.set_page_config(
    page_title="Trading Star Market Radar",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Trading Star Market Radar")
st.caption("Historical Wave Intelligence | Research Dashboard")

st.divider()


# -----------------------------------------
# DATA PROCESSING
# -----------------------------------------

def normalize_columns(df):

    df.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in df.columns
    ]

    aliases = {
        "date": ["date", "datetime", "timestamp", "time"],
        "open": ["open", "o"],
        "high": ["high", "h"],
        "low": ["low", "l"],
        "close": ["close", "c", "adj_close"],
        "volume": ["volume", "vol", "tick_volume"]
    }

    rename_map = {}

    for standard, possible_names in aliases.items():
        for name in possible_names:
            if name in df.columns:
                rename_map[name] = standard
                break

    df = df.rename(columns=rename_map)

    required = ["date", "open", "high", "low", "close"]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing)
        )

    if "volume" not in df.columns:
        df["volume"] = 0

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    numeric_columns = [
        "open", "high", "low", "close", "volume"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "date", "open", "high",
            "low", "close"
        ]
    )

    df = df.sort_values("date")
    df = df.drop_duplicates(
        subset=["date"],
        keep="last"
    )

    df = df.reset_index(drop=True)

    if len(df) < 20:
        raise ValueError(
            "At least 20 valid candles are required."
        )

    invalid = (
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    )

    if invalid.any():
        raise ValueError(
            "Invalid OHLC candle data detected. "
            "Please check your CSV file."
        )

    return df


# -----------------------------------------
# ATR CALCULATION
# -----------------------------------------

def calculate_atr(df, period=14):

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]

    tr2 = (
        df["high"] - previous_close
    ).abs()

    tr3 = (
        df["low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.rolling(
        period,
        min_periods=period
    ).mean()


# -----------------------------------------
# CONFIRMED PIVOT DETECTOR
# -----------------------------------------

def detect_swings(df, left=3, right=3):

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()

    candidates = []

    for i in range(left, len(df) - right):

        high_window = highs[
            i-left:i+right+1
        ]

        low_window = lows[
            i-left:i+right+1
        ]

        current_high = highs[i]
        current_low = lows[i]

        # Unique confirmed pivot high
        if (
            current_high == np.max(high_window)
            and np.sum(high_window == current_high) == 1
        ):
            candidates.append({
                "index": i,
                "type": "HIGH",
                "price": float(current_high)
            })

        # Unique confirmed pivot low
        if (
            current_low == np.min(low_window)
            and np.sum(low_window == current_low) == 1
        ):
            candidates.append({
                "index": i,
                "type": "LOW",
                "price": float(current_low)
            })

    candidates.sort(
        key=lambda x: x["index"]
    )

    # Keep alternating swing types.
    # If two same-type pivots occur consecutively,
    # retain only the more extreme one.

    swings = []

    for point in candidates:

        if not swings:
            swings.append(point)
            continue

        previous = swings[-1]

        if point["type"] != previous["type"]:
            swings.append(point)

        else:

            if point["type"] == "HIGH":
                if point["price"] > previous["price"]:
                    swings[-1] = point

            elif point["type"] == "LOW":
                if point["price"] < previous["price"]:
                    swings[-1] = point

    return swings


# -----------------------------------------
# SWING STRUCTURE CLASSIFICATION
# -----------------------------------------

def classify_swings(swings):

    previous_high = None
    previous_low = None

    for point in swings:

        if point["type"] == "HIGH":

            if previous_high is None:
                point["structure"] = "INITIAL HIGH"

            elif point["price"] > previous_high:
                point["structure"] = "HH"

            else:
                point["structure"] = "LH"

            previous_high = point["price"]

        else:

            if previous_low is None:
                point["structure"] = "INITIAL LOW"

            elif point["price"] > previous_low:
                point["structure"] = "HL"

            else:
                point["structure"] = "LL"

            previous_low = point["price"]

    return swings


# -----------------------------------------
# SIDEBAR
# -----------------------------------------

st.sidebar.header("Market Settings")

market = st.sidebar.selectbox(
    "Select Market",
    [
        "XAUUSD",
        "NIFTY 50",
        "BANK NIFTY",
        "NSE STOCK",
        "FOREX"
    ]
)

timeframe = st.sidebar.selectbox(
    "Select Timeframe",
    ["1H", "30M", "15M"]
)

st.sidebar.caption(
    "Upload historical OHLCV CSV data for research."
)


# -----------------------------------------
# CSV UPLOAD
# -----------------------------------------

st.subheader("Historical Market Data")

uploaded_file = st.file_uploader(
    "Upload OHLCV CSV File",
    type=["csv"]
)


if uploaded_file is None:

    st.info(
        "Please upload a CSV file containing "
        "Date, Open, High, Low and Close columns."
    )

    st.markdown("### Required CSV Format")

    st.code(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-01-01,100,105,98,103,15000\n"
        "2026-01-02,103,108,101,106,18000"
    )

else:

    try:

        # ---------------------------------
        # LOAD AND VALIDATE DATA
        # ---------------------------------

        raw_data = pd.read_csv(uploaded_file)

        data = normalize_columns(raw_data)

        data["ATR"] = calculate_atr(data)

        st.success(
            "Historical data successfully loaded "
            "and validated."
        )

        st.divider()

        # ---------------------------------
        # MARKET SUMMARY
        # ---------------------------------

        st.subheader("Market Overview")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Market",
            market
        )

        col2.metric(
            "Timeframe",
            timeframe
        )

        col3.metric(
            "Total Candles",
            len(data)
        )

        col4.metric(
            "Latest Close",
            f"{data['close'].iloc[-1]:.4f}"
        )

        # ---------------------------------
        # CANDLESTICK CHART
        # ---------------------------------

        st.subheader("Historical Price Chart")

        candle_fig = go.Figure()

        candle_fig.add_trace(
            go.Candlestick(
                x=data["date"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                name="Price"
            )
        )

        candle_fig.update_layout(
            template="plotly_dark",
            height=500,
            xaxis_title="Date",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(
            candle_fig,
            use_container_width=True
        )

        # ---------------------------------
        # WAVE DETECTION
        # ---------------------------------

        st.divider()

        st.subheader(
            "Advanced Wave Structure Intelligence"
        )

        swings = detect_swings(
            data,
            left=3,
            right=3
        )

        swings = classify_swings(swings)

        if len(swings) >= 2:

            # ---------------------------------
            # WAVE PERFORMANCE
            # ---------------------------------

            wave_rows = []

            for j in range(1, len(swings)):

                a = swings[j - 1]
                b = swings[j]

                difference = (
                    b["price"] - a["price"]
                )

                duration = (
                    b["index"] - a["index"]
                )

                atr_value = data["ATR"].iloc[
                    b["index"]
                ]

                if (
                    pd.notna(atr_value)
                    and atr_value > 0
                ):
                    atr_multiple = (
                        abs(difference) / atr_value
                    )
                else:
                    atr_multiple = np.nan

                velocity = (
                    abs(difference) / duration
                    if duration > 0
                    else np.nan
                )

                movement_percent = (
                    abs(difference) / a["price"] * 100
                    if a["price"] != 0
                    else np.nan
                )

                wave_rows.append({

                    "Wave": j,

                    "Direction": (
                        "BULLISH"
                        if difference > 0
                        else "BEARISH"
                    ),

                    "Structure": (
                        a["structure"]
                        + " → "
                        + b["structure"]
                    ),

                    "Start Price": round(
                        a["price"], 5
                    ),

                    "End Price": round(
                        b["price"], 5
                    ),

                    "Movement": round(
                        abs(difference), 5
                    ),

                    "Movement %": round(
                        movement_percent, 3
                    ),

                    "Duration": duration,

                    "Velocity": (
                        round(velocity, 5)
                        if pd.notna(velocity)
                        else None
                    ),

                    "ATR Multiple": (
                        round(atr_multiple, 2)
                        if pd.notna(atr_multiple)
                        else None
                    )
                })

            waves = pd.DataFrame(wave_rows)

            bullish_count = int(
                (waves["Direction"] == "BULLISH").sum()
            )

            bearish_count = int(
                (waves["Direction"] == "BEARISH").sum()
            )

            # ---------------------------------
            # WAVE METRICS
            # ---------------------------------

            m1, m2, m3 = st.columns(3)

            m1.metric(
                "Total Waves",
                len(waves)
            )

            m2.metric(
                "Bullish Waves",
                bullish_count
            )

            m3.metric(
                "Bearish Waves",
                bearish_count
            )

            # ---------------------------------
            # SWING STRUCTURE TABLE
            # ---------------------------------

            st.subheader("Swing Structure")

            structure_data = pd.DataFrame([

                {
                    "Time": data["date"].iloc[
                        point["index"]
                    ],

                    "Swing Type": point["type"],

                    "Price": round(
                        point["price"], 5
                    ),

                    "Classification": point["structure"]
                }

                for point in swings

            ])

            st.dataframe(
                structure_data.tail(30),
                use_container_width=True,
                hide_index=True
            )

            # ---------------------------------
            # WAVE PERFORMANCE TABLE
            # ---------------------------------

            st.subheader("Wave Performance Table")

            st.dataframe(
                waves.tail(30),
                use_container_width=True,
                hide_index=True
            )

            # ---------------------------------
            # ECG WAVE MONITOR
            # ---------------------------------

            st.subheader("Market ECG Wave Monitor")

            wave_fig = go.Figure()

            wave_fig.add_trace(
                go.Scatter(
                    x=[
                        data["date"].iloc[p["index"]]
                        for p in swings
                    ],

                    y=[
                        p["price"]
                        for p in swings
                    ],

                    mode="lines+markers+text",

                    text=[
                        p["structure"]
                        for p in swings
                    ],

                    textposition="top center",

                    line=dict(
                        color="#00E5A8",
                        width=2
                    ),

                    marker=dict(
                        size=8
                    ),

                    name="Confirmed Wave Structure"
                )
            )

            wave_fig.update_layout(
                template="plotly_dark",
                height=450,
                xaxis_title="Date",
                yaxis_title="Price"
            )

            st.plotly_chart(
                wave_fig,
                use_container_width=True
            )

            # ---------------------------------
            # MARKET STRUCTURE OBSERVATION
            # ---------------------------------

            st.subheader(
                "Market Structure Observation"
            )

            recent = [
                p["structure"]
                for p in swings[-6:]
            ]

            has_hh = "HH" in recent
            has_hl = "HL" in recent

            has_lh = "LH" in recent
            has_ll = "LL" in recent

            if has_hh and has_hl:

                st.success(
                    "Higher High and Higher Low "
                    "structures detected. "
                    "Bullish structure is present "
                    "in the recent confirmed swings."
                )

            elif has_lh and has_ll:

                st.warning(
                    "Lower High and Lower Low "
                    "structures detected. "
                    "Bearish structure is present "
                    "in the recent confirmed swings."
                )

            else:

                st.info(
                    "Mixed or developing structure. "
                    "Wait for additional confirmed swings."
                )

            st.caption(
                "Structure observation only. "
                "This is not a trading signal or "
                "a prediction of the next market move."
            )

        else:

            st.warning(
                "Insufficient confirmed swings. "
                "Upload more historical candles."
            )

        # ---------------------------------
        # DATA PREVIEW
        # ---------------------------------

        with st.expander("View Uploaded Historical Data"):

            st.dataframe(
                data.tail(50),
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:

        st.error(
            f"Market Radar Error: {e}"
        )

        st.info(
            "Please check your CSV columns and data format."
        )


# -----------------------------------------
# FOOTER
# -----------------------------------------

st.divider()

st.caption(
    "TRADING STAR | MARKET RADAR | RESEARCH V1.2"
)
