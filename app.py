
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Trading Star Market Radar",
    page_icon="📡",
    layout="wide"
)

st.title("📡 TRADING STAR — MARKET RADAR")
st.caption("Multi-Market Wave Intelligence | Research V1.1")

st.sidebar.header("Market Settings")

market = st.sidebar.selectbox(
    "Select Market",
    ["XAUUSD", "NIFTY 50", "BANK NIFTY", "NSE STOCK"]
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["1H", "30M", "15M"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Research Mode | No live trading signals")

st.subheader("Historical Data Centre")

uploaded_file = st.file_uploader(
    "Upload OHLCV CSV File",
    type=["csv"]
)

def find_column(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None

if uploaded_file is not None:

    try:
        df = pd.read_csv(uploaded_file)
        df.columns = [
            str(c).strip().lower().replace(" ", "_")
            for c in df.columns
        ]

        date_col = find_column(
            df, ["datetime", "timestamp", "date", "time"]
        )
        open_col = find_column(df, ["open", "o"])
        high_col = find_column(df, ["high", "h"])
        low_col = find_column(df, ["low", "l"])
        close_col = find_column(df, ["close", "c"])
        volume_col = find_column(
            df, ["volume", "vol", "tick_volume"]
        )

        required = [
            date_col, open_col, high_col,
            low_col, close_col
        ]

        if any(c is None for c in required):
            st.error(
                "Required columns: Date/Datetime, Open, "
                "High, Low, Close. Please check your CSV."
            )
            st.write("Available columns:", list(df.columns))
            st.stop()

        data = pd.DataFrame({
            "Date": pd.to_datetime(df[date_col], errors="coerce"),
            "Open": pd.to_numeric(df[open_col], errors="coerce"),
            "High": pd.to_numeric(df[high_col], errors="coerce"),
            "Low": pd.to_numeric(df[low_col], errors="coerce"),
            "Close": pd.to_numeric(df[close_col], errors="coerce"),
        })

        if volume_col:
            data["Volume"] = pd.to_numeric(
                df[volume_col], errors="coerce"
            )
        else:
            data["Volume"] = np.nan

        data = (
            data.dropna(subset=[
                "Date", "Open", "High", "Low", "Close"
            ])
            .sort_values("Date")
            .drop_duplicates(subset="Date", keep="last")
            .reset_index(drop=True)
        )

        data = data[
            (data["High"] >= data["Low"]) &
            (data["High"] >= data["Open"]) &
            (data["High"] >= data["Close"]) &
            (data["Low"] <= data["Open"]) &
            (data["Low"] <= data["Close"])
        ].copy()

        if len(data) < 30:
            st.error("At least 30 valid candles are required.")
            st.stop()

        # ATR Calculation
        previous_close = data["Close"].shift(1)

        tr = pd.concat([
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs()
        ], axis=1).max(axis=1)

        data["ATR"] = tr.rolling(14).mean()

        # Confirmed Pivot Detection
        left = 3
        right = 3
        candidates = []

        for i in range(left, len(data) - right):

            window = data.iloc[i-left:i+right+1]

            is_high = (
                data["High"].iloc[i] == window["High"].max()
                and (window["High"] == data["High"].iloc[i]).sum() == 1
            )

            is_low = (
                data["Low"].iloc[i] == window["Low"].min()
                and (window["Low"] == data["Low"].iloc[i]).sum() == 1
            )

            if is_high:
                candidates.append({
                    "index": i,
                    "type": "HIGH",
                    "price": data["High"].iloc[i]
                })

            if is_low:
                candidates.append({
                    "index": i,
                    "type": "LOW",
                    "price": data["Low"].iloc[i]
                })

        candidates.sort(key=lambda x: x["index"])

        # Keep alternating swing points
        swings = []

        for point in candidates:
            if not swings:
                swings.append(point)
                continue

            previous = swings[-1]

            if point["type"] == previous["type"]:
                if point["type"] == "HIGH":
                    if point["price"] > previous["price"]:
                        swings[-1] = point
                else:
                    if point["price"] < previous["price"]:
                        swings[-1] = point
            elif point["index"] != previous["index"]:
                swings.append(point)

        # Market Overview
        st.success("Historical Data Loaded Successfully")

        c1, c2, c3 = st.columns(3)
        c1.metric("Market", market)
        c2.metric("Timeframe", timeframe)
        c3.metric("Valid Candles", len(data))

        st.subheader("Price Structure")

        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=data["Date"],
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price"
        ))

        if swings:
            sx = [data["Date"].iloc[p["index"]] for p in swings]
            sy = [p["price"] for p in swings]
            colors = [
                "#00C853" if p["type"] == "LOW" else "#FF5252"
                for p in swings
            ]

            fig.add_trace(go.Scatter(
                x=sx,
                y=sy,
                mode="lines+markers",
                name="Wave Structure",
                line=dict(color="#FFA726", width=2),
                marker=dict(color=colors, size=9)
            ))

        fig.update_layout(
            template="plotly_dark",
            height=550,
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(fig, use_container_width=True)

        
        # ADVANCED WAVE STRUCTURE INTELLIGENCE

        st.subheader("Advanced Wave Intelligence")

        # Classify swing highs and lows
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

        # Build wave research table
        wave_rows = []

        for j in range(1, len(swings)):
            a = swings[j-1]
            b = swings[j]

            difference = b["price"] - a["price"]
            duration = b["index"] - a["index"]

            atr_value = data["ATR"].iloc[b["index"]]

            atr_multiple = (
                abs(difference) / atr_value
                if pd.notna(atr_value) and atr_value > 0
                else np.nan
            )

            velocity = (
                abs(difference) / duration
                if duration > 0 else np.nan
            )

            wave_rows.append({
                "Wave": j,
                "Direction": (
                    "BULLISH" if difference > 0 else "BEARISH"
                ),
                "Structure": (
                    a["structure"] + " → " + b["structure"]
                ),
                "Start Price": round(a["price"], 5),
                "End Price": round(b["price"], 5),
                "Movement": round(abs(difference), 5),
                "Movement %": round(
                    abs(difference) / a["price"] * 100, 3
                ),
                "Duration": duration,
                "Velocity": round(velocity, 5),
                "ATR Multiple": (
                    round(atr_multiple, 2)
                    if pd.notna(atr_multiple) else None
                )
            })

        if wave_rows:

            waves = pd.DataFrame(wave_rows)

            bullish_count = (
                waves["Direction"] == "BULLISH"
            ).sum()

            bearish_count = (
                waves["Direction"] == "BEARISH"
            ).sum()

            c1, c2, c3 = st.columns(3)

            c1.metric("Total Waves", len(waves))
            c2.metric("Bullish Waves", int(bullish_count))
            c3.metric("Bearish Waves", int(bearish_count))

            st.markdown("### Swing Structure")

            structure_data = pd.DataFrame([
                {
                    "Time": data["Date"].iloc[p["index"]],
                    "Swing Type": p["type"],
                    "Price": round(p["price"], 5),
                    "Classification": p["structure"]
                }
                for p in swings
            ])

            st.dataframe(
                structure_data.tail(30),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("### Wave Performance Table")

            st.dataframe(
                waves.tail(30),
                use_container_width=True,
                hide_index=True
            )

            # ECG-style wave graph
            st.markdown("### Market ECG Wave Monitor")

            wave_fig = go.Figure()

            wave_fig.add_trace(go.Scatter(
                x=[p["index"] for p in swings],
                y=[p["price"] for p in swings],
                mode="lines+markers+text",
                text=[p["structure"] for p in swings],
                textposition="top center",
                line=dict(color="#00E5A8", width=2),
                marker=dict(size=8),
                name="Confirmed Wave Structure"
            ))

            wave_fig.update_layout(
                template="plotly_dark",
                height=400,
                xaxis_title="Candle Index",
                yaxis_title="Price"
            )

            st.plotly_chart(
                wave_fig,
                use_container_width=True
            )

            # Basic structural observation
            recent = [p["structure"] for p in swings[-6:]]

            st.markdown("### Market Structure Observation")

            if recent.count("HH") >= 1 and recent.count("HL") >= 1:
                st.success(
                    "Higher High / Higher Low structures detected. "
                    "Review bullish structure."
                )

            elif recent.count("LH") >= 1 and recent.count("LL") >= 1:
                st.warning(
                    "Lower High / Lower Low structures detected. "
                    "Review bearish structure."
                )

            else:
                st.info(
                    "Mixed or developing structure. "
                    "Wait for additional confirmed swings."
                )

        else:
            st.warning("Insufficient confirmed waves for analysis.")


st.divider()
st.caption("TRADING STAR | MARKET RADAR | RESEARCH V1.1")
