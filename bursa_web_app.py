import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from urllib.parse import quote
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout, search_bursa, get_top_breakouts, KLCI_COMPONENTS, get_futures_breakouts

# --- PAGE CONFIG ---
st.set_page_config(page_title="Bursa Breakout Analyzer", layout="wide", page_icon="📈")

# --- QUERY PARAMS (Popup Chart Mode) ---
def _get_query_param(name: str):
    try:
        v = st.query_params.get(name)
        if isinstance(v, list):
            return v[0] if v else None
        return v
    except Exception:
        try:
            return st.experimental_get_query_params().get(name, [None])[0]
        except Exception:
            return None


def _render_chart(symbol: str):
    df_chart, name_chart = get_stock_data(symbol, period="5y")

    if df_chart is None or df_chart.empty:
        st.warning(f"5-year data unavailable for {symbol}. Trying 1-year data...")
        df_chart, name_chart = get_stock_data(symbol, period="1y")

    if df_chart is None or df_chart.empty:
        st.error(f"Could not load any historical data for {symbol}.")
        return

    df_chart["SMA20"] = df_chart["Close"].rolling(window=20).mean()
    df_chart["SMA50"] = df_chart["Close"].rolling(window=50).mean()
    plot_df = df_chart.tail(100)

    if plot_df.empty:
        st.error("Historical price data is too short for charting.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=plot_df.index,
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="Market",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df.index,
            y=plot_df["SMA20"],
            line=dict(color="orange", width=1.5),
            name="SMA 20",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df.index,
            y=plot_df["SMA50"],
            line=dict(color="blue", width=1.5),
            name="SMA 50",
        )
    )
    fig.update_layout(
        title=f"{name_chart} ({symbol}) - Price Action",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        height=650,
    )
    st.plotly_chart(fig, use_container_width=True)

    vol_colors = [
        "green" if plot_df["Close"].iloc[i] >= plot_df["Open"].iloc[i] else "red"
        for i in range(len(plot_df))
    ]
    vol_fig = go.Figure(
        go.Bar(x=plot_df.index, y=plot_df["Volume"], name="Volume", marker_color=vol_colors)
    )
    vol_fig.update_layout(title="Trading Volume", height=300, template="plotly_white")
    st.plotly_chart(vol_fig, use_container_width=True)


chart_symbol = _get_query_param("chart")
popup_mode = _get_query_param("popup")

# --- UI ---
st.title("📈 Bursa Malaysia Breakout Analyzer")
st.subheader("Dynamic Market Scanner & Research Tool")
st.markdown("---")

if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "refresh_seconds" not in st.session_state:
    st.session_state.refresh_seconds = 60
if "auto_top10" not in st.session_state:
    st.session_state.auto_top10 = True

if not chart_symbol:
    st.sidebar.header("⚙️ Auto Refresh")
    st.session_state.auto_refresh = st.sidebar.checkbox(
        "Enable auto-refresh", value=bool(st.session_state.auto_refresh)
    )
    st.session_state.refresh_seconds = st.sidebar.selectbox(
        "Refresh interval (seconds)",
        options=[15, 30, 60, 120, 300],
        index=[15, 30, 60, 120, 300].index(int(st.session_state.refresh_seconds))
        if int(st.session_state.refresh_seconds) in [15, 30, 60, 120, 300]
        else 2,
    )
    st.session_state.auto_top10 = st.sidebar.checkbox(
        "Auto-update Top 10 on refresh", value=bool(st.session_state.auto_top10)
    )

    if st.session_state.auto_refresh:
        st.markdown(
            f"<meta http-equiv='refresh' content='{int(st.session_state.refresh_seconds)}'>",
            unsafe_allow_html=True,
        )

# Popup/new-tab chart view (opened from table clicks)
if chart_symbol:
    with st.spinner(f"Loading chart for {chart_symbol}..."):
        _render_chart(chart_symbol)
    st.markdown(f"[Back to Dashboard](/)")
    st.stop()

# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    with st.spinner("Initializing Market Discovery..."):
        # Get top 10 breakouts from KLCI components on first load
        top_breakouts = get_top_breakouts(limit=10)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
elif not chart_symbol and bool(st.session_state.auto_top10):
    with st.spinner("Refreshing Top 10 breakouts..."):
        top_breakouts = get_top_breakouts(limit=10)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]

# Sidebar for adding stocks (hide in popup mode)
if not popup_mode:
    st.sidebar.header("🔍 Market Discovery")
    st.sidebar.info("Scans 30 major KLCI stocks to identify the strongest technical breakouts.")

    if st.sidebar.button("🔄 Refresh Market Discovery", use_container_width=True):
        with st.spinner("Re-scanning KLCI components..."):
            top_breakouts = get_top_breakouts(limit=10)
            st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
            st.success("Dashboard updated!")
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("➕ Add Custom Stock")
    new_stock = st.sidebar.text_input("Enter Name, Code or Futures (e.g., GENTING, 0166, FKLI)")
    if st.sidebar.button("Add to Watchlist", use_container_width=True):
        ticker = search_bursa(new_stock)
        if ticker:
            if ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(ticker)
                st.success(f"Added {ticker}!")
                st.rerun()
            else:
                st.info(f"{ticker} is already in your list.")
        else:
            st.error("Could not find stock. Try using the exact code (e.g., 5347).")

    if st.sidebar.button("🗑️ Reset to Top 10", use_container_width=True):
        top_breakouts = get_top_breakouts(limit=10)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.rerun()

# --- MAIN DASHBOARD TABS ---
tab_stocks, tab_futures = st.tabs(["📊 Stock Breakouts", "⛓️ Futures Monitoring"])

with tab_stocks:
    data_rows = []
    # Use a spinner for the load
    with st.spinner("Fetching latest live prices..."):
        for t in st.session_state.watchlist:
            # Skip futures in the stock tab if they were added manually
            if "=F" in t: continue
            df, name = get_stock_data(t, period="1y")
            if df is not None and not df.empty:
                analysis = analyze_breakout(t, df, name)
                if analysis:
                    data_rows.append(analysis)

    if data_rows:
        # Top Metrics
        total_breakouts = len([r for r in data_rows if r['score'] >= 4])
        avg_rsi = sum([r['rsi'] for r in data_rows]) / len(data_rows)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Strong Breakouts (Score 4+)", total_breakouts)
        col2.metric("Watchlist Count", len(data_rows))
        col3.metric("Avg Watchlist RSI", f"{avg_rsi:.1f}")

        st.markdown("### 📊 Live Breakout Analysis")
        
        # Prepare display dataframe
        display_rows = []
        for r in data_rows:
            link = f"?chart={quote(r['ticker'])}&popup=1"
            linked_name = f'<a href="{link}" target="_blank" rel="noopener noreferrer">{r["name"]}</a>'
            display_rows.append({
                "Ticker": r['ticker'],
                "Name": linked_name,
                "Price (RM)": r['price'],
                "Score": f"{r['score']}/5",
                "RSI": r['rsi'],
                "Status": "🔥 STRONG" if r['score'] >= 4 else ("⚖️ NEUTRAL" if r['score'] >= 2 else "❄️ WEAK"),
                "Catalyst / Insight": r['catalyst'] if r['score'] >= 3 else r['analysis']
            })
        
        df_display = pd.DataFrame(display_rows)
        st.caption("Tip: click the stock name to open its chart in a new window/tab.")
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.warning("No data found. Please click 'Refresh Market Discovery' or add valid tickers.")

with tab_futures:
    st.markdown("### ⛓️ Malaysian Futures Dashboard")
    st.info("Monitoring FKLI, FCPO, and FM70 for technical breakouts.")
    
    futures_data = []
    with st.spinner("Analyzing Futures market..."):
        futures_data = get_futures_breakouts()
    
    if futures_data:
        futures_display = []
        for r in futures_data:
            link = f"?chart={quote(r['ticker'])}&popup=1"
            linked_name = f'<a href="{link}" target="_blank" rel="noopener noreferrer">{r["name"]}</a>'
            futures_display.append({
                "Future Contract": linked_name,
                "Ticker": r['ticker'],
                "Last Price": r['price'],
                "Breakout Score": f"{r['score']}/5",
                "RSI": r['rsi'],
                "Momentum": "🚀 BULLISH" if r['score'] >= 4 else ("⚖️ SIDEWAYS" if r['score'] >= 2 else "📉 BEARISH"),
                "Technical View": r['analysis']
            })
        
        df_futures = pd.DataFrame(futures_display)
        st.caption("Tip: click the futures contract name to open its chart in a new window/tab.")
        st.markdown(df_futures.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # Add a note about futures
        st.caption("Note: Futures analysis uses daily settlement prices. Breakout scores 4+ indicate high trend momentum.")
    else:
        st.error("Could not fetch futures data. Please check your internet connection.")

if not popup_mode:
    st.sidebar.markdown("---")
    show_debug = st.sidebar.checkbox("Show Debug Info")
    if show_debug:
        st.sidebar.write("Current Watchlist:", st.session_state.watchlist)

    st.sidebar.info("Market Discovery scans 30 major KLCI stocks every time the dashboard is initialized or refreshed.")

# --- TECHNICAL EXPLANATION ---
with st.expander("ℹ️ How is the Breakout Score calculated?"):
    st.markdown("""
    The **Breakout Score (0-5)** is a technical indicator that measures the strength of a stock's upward momentum. It is calculated as follows:
    
    1.  **Trend Alignment (+1 point)**: Awarded if the current price is above both the **20-day** and **50-day** Simple Moving Averages (SMA). This indicates a healthy medium-term uptrend.
    2.  **Volume Surge (+2 points)**: Awarded if today's trading volume is at least **1.5x higher** than the average volume of the last 20 days. High volume confirms that big institutional players are entering the stock.
    3.  **Price Breakout (+2 points)**: Awarded if the current price is higher than the maximum price reached in the last 20 trading days. This indicates the stock has broken through a recent resistance level.
    
    **Status Legend:**
    *   🔥 **STRONG (Score 4-5)**: High probability of a sustained move.
    *   ⚖️ **NEUTRAL (Score 2-3)**: Showing signs of interest but lacks full confirmation.
    *   ❄️ **WEAK (Score 0-1)**: No significant breakout signals detected.
    """)
