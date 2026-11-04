
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

        # Wave Research
        st.subheader("Historical Wave Analysis")

        wave_rows = []

        for j in range(1, len(swings)):
            a = swings[j-1]
            b = swings[j]

            difference = b["price"] - a["price"]

            wave_rows.append({
                "Wave": j,
                "Direction": (
                    "BULLISH" if difference > 0 else "BEARISH"
                ),
                "Start": round(a["price"], 5),
                "End": round(b["price"], 5),
                "Movement": round(abs(difference), 5),
                "Candles": b["index"] - a["index"]
            })

        if wave_rows:
            waves = pd.DataFrame(wave_rows)

            st.dataframe(
                waves.tail(30),
                use_container_width=True,
                hide_index=True
            )

            st.subheader("Wave ECG Monitor")

            wave_fig = go.Figure()

            wave_fig.add_trace(go.Scatter(
                x=list(range(len(swings))),
                y=[p["price"] for p in swings],
                mode="lines+markers",
                line=dict(color="#00E5A8", width=2),
                name="Market Wave"
            ))

            wave_fig.update_layout(
                template="plotly_dark",
                height=300,
                xaxis_title="Wave Sequence",
                yaxis_title="Price"
            )

            st.plotly_chart(
                wave_fig,
                use_container_width=True
            )

            st.metric("Detected Waves", len(waves))

        else:
            st.warning("No confirmed wave sequence detected.")

        st.info(
            "Research note: The latest right-side candles are "
            "not confirmed pivots. This is a historical structure "
            "prototype, not a future direction prediction."
        )

    except Exception as e:
        st.error(f"Data processing error: {e}")

else:
    st.info(
        "Upload a historical OHLCV CSV file to begin "
        "Wave Detection Research."
    )

st.divider()
st.caption("TRADING STAR | MARKET RADAR | RESEARCH V1.1")
