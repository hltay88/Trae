import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout, analyze_breakout_v2, search_bursa, get_top_breakouts, KLCI_COMPONENTS, get_futures_breakouts

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
    def _is_today_kl(ts) -> bool:
        try:
            t = pd.Timestamp(ts)
            if t.tz is None:
                t = t.tz_localize("Asia/Kuala_Lumpur")
            else:
                t = t.tz_convert("Asia/Kuala_Lumpur")
            return t.normalize() == pd.Timestamp.now(tz="Asia/Kuala_Lumpur").normalize()
        except Exception:
            return False

    def _tradingview_url(sym: str) -> str | None:
        try:
            s = str(sym).upper().strip()
            tv_map = {"FKLI=F": "MYX:FKLI1!", "FCPO=F": "MYX:FCPO1!"}
            if s in tv_map:
                tv_symbol = tv_map[s]
            elif s.endswith(".KL"):
                code = s.split(".")[0]
                tv_symbol = f"MYX:{code}"
            else:
                return None
            return f"https://www.tradingview.com/chart/?symbol={quote(tv_symbol, safe='')}"
        except Exception:
            return None

    def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
        if cols:
            df = df.dropna(subset=cols)

        if "Close" in df.columns:
            df = df[pd.to_numeric(df["Close"], errors="coerce").fillna(0) > 0]

        if "Volume" in df.columns and len(df) >= 2:
            try:
                v_last = float(df["Volume"].iloc[-1])
                v_prev = float(df["Volume"].iloc[-2])
                if v_last == 0.0 and v_prev > 0.0 and not _is_today_kl(df.index[-1]):
                    df = df.iloc[:-1]
            except Exception:
                pass

        return df

    def _render_tradingview(symbol_tv: str, height: int = 720):
        html = f"""
<div class="tradingview-widget-container">
  <div id="tradingview_widget"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "{symbol_tv}",
    "interval": "D",
    "timezone": "Asia/Kuala_Lumpur",
    "theme": "dark",
    "style": "1",
    "locale": "en",
    "enable_publishing": false,
    "hide_top_toolbar": true,
    "hide_side_toolbar": true,
    "allow_symbol_change": false,
    "save_image": false,
    "container_id": "tradingview_widget"
  }});
  </script>
</div>
"""
        components.html(html, height=height, scrolling=False)

    if symbol in {"FKLI=F", "FCPO=F"}:
        tv_map = {"FKLI=F": "MYX:FKLI1!", "FCPO=F": "MYX:FCPO1!"}
        tv_url = _tradingview_url(symbol)
        if tv_url:
            st.markdown(f"[Open this chart in TradingView (live)]({tv_url})")
        _render_tradingview(tv_map[symbol])
        st.caption("If the chart is blank, click the TradingView logo to open the full chart on TradingView.")
        return

    tv_url = _tradingview_url(symbol)
    if tv_url:
        st.markdown(f"[Open this chart in TradingView (live)]({tv_url})")

    df_chart, name_chart = get_stock_data(symbol, period="5y")

    if df_chart is None or df_chart.empty:
        st.warning(f"5-year data unavailable for {symbol}. Trying 1-year data...")
        df_chart, name_chart = get_stock_data(symbol, period="1y")

    df_chart = _clean_ohlcv(df_chart)

    if df_chart is None or df_chart.empty:
        st.error(f"Could not load any historical data for {symbol}.")
        return

    if "Volume" in df_chart.columns:
        try:
            df_chart = df_chart.copy()
            df_chart["Volume"] = pd.to_numeric(df_chart["Volume"], errors="coerce").fillna(0).astype("int64")
        except Exception:
            pass

    df_chart["SMA20"] = df_chart["Close"].rolling(window=20).mean()
    df_chart["SMA50"] = df_chart["Close"].rolling(window=50).mean()
    plot_df = df_chart

    if plot_df.empty:
        st.error("Historical price data is too short for charting.")
        return

    try:
        plot_df = plot_df.copy()
        if plot_df.index.tz is not None:
            plot_df.index = plot_df.index.tz_convert("Asia/Kuala_Lumpur").tz_localize(None)
    except Exception:
        pass

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
        xaxis_rangeslider_visible=True,
        template="plotly_dark",
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
    vol_fig.update_layout(title="Trading Volume", height=300, template="plotly_dark")
    vol_fig.update_yaxes(tickformat="~s")
    st.plotly_chart(vol_fig, use_container_width=True)


chart_symbol = _get_query_param("chart")
popup_mode = _get_query_param("popup")

if "breakout_model" not in st.session_state:
    st.session_state.breakout_model = "v2"
if "universe_mode" not in st.session_state:
    st.session_state.universe_mode = "curated"

# --- UI ---
if not chart_symbol:
    st.title("📈 Bursa Malaysia Breakout Analyzer")
    st.subheader("Dynamic Market Scanner & Research Tool")
    st.markdown("---")

st.markdown(
    """
<style>
table { width: 100%; border-collapse: collapse; color: var(--text-color); }
thead th { background: var(--secondary-background-color); color: var(--text-color); border-bottom: 1px solid rgba(255,255,255,0.12); padding: 8px; text-align: left; }
tbody td { color: var(--text-color); border-bottom: 1px solid rgba(255,255,255,0.08); padding: 8px; }
tbody tr:hover { background: rgba(255,255,255,0.04); }
a { color: var(--primary-color); text-decoration: none; }
a:hover { text-decoration: underline; }
</style>
""",
    unsafe_allow_html=True,
)

# Popup/new-tab chart view (opened from table clicks)
if chart_symbol:
    st.markdown(
        f"### {chart_symbol} — Chart",
    )
    st.caption("This is an in-app chart view. Use the link below to return to the dashboard.")
    with st.spinner(f"Loading chart for {chart_symbol}..."):
        _render_chart(chart_symbol)
    st.markdown("[Back to Dashboard](/)")
    st.stop()

# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    with st.spinner("Initializing Market Discovery..."):
        top_breakouts = get_top_breakouts(limit=20, model=st.session_state.breakout_model, universe_mode=st.session_state.universe_mode)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]

# Sidebar for adding stocks (hide in popup mode)
if not popup_mode:
    st.sidebar.header("🔍 Market Discovery")
    st.sidebar.info("Scans a Bursa universe to identify the strongest technical breakouts.")

    universe_label = st.sidebar.radio(
        "Universe",
        ["Curated (Fast)", "From File (Full)"],
        index=0 if st.session_state.universe_mode == "curated" else 1,
        horizontal=True,
    )
    selected_universe = "curated" if universe_label.startswith("Curated") else "file"
    if selected_universe != st.session_state.universe_mode:
        st.session_state.universe_mode = selected_universe
        with st.spinner("Refreshing list for selected universe..."):
            top_breakouts = get_top_breakouts(limit=20, model=st.session_state.breakout_model, universe_mode=st.session_state.universe_mode)
            st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.rerun()
    if st.session_state.universe_mode == "file":
        st.sidebar.caption("Universe source: bursa_universe.csv in the app folder. Add one ticker per line (e.g., 6742.KL or 6742).")

    model_label = st.sidebar.radio(
        "Breakout Model",
        ["Stronger (V2)", "Original (V1)"],
        index=0 if st.session_state.breakout_model == "v2" else 1,
        horizontal=True,
    )
    selected_model = "v2" if model_label.startswith("Stronger") else "v1"
    if selected_model != st.session_state.breakout_model:
        st.session_state.breakout_model = selected_model
        with st.spinner("Refreshing list for selected model..."):
            top_breakouts = get_top_breakouts(limit=20, model=st.session_state.breakout_model, universe_mode=st.session_state.universe_mode)
            st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.rerun()

    if st.sidebar.button("🔄 Refresh Market Discovery", use_container_width=True):
        with st.spinner("Re-scanning KLCI components..."):
            top_breakouts = get_top_breakouts(limit=20, model=st.session_state.breakout_model, universe_mode=st.session_state.universe_mode)
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

    if st.sidebar.button("🗑️ Reset to Top 20", use_container_width=True):
        top_breakouts = get_top_breakouts(limit=20, model=st.session_state.breakout_model, universe_mode=st.session_state.universe_mode)
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.rerun()

# --- MAIN DASHBOARD TABS ---
tab_stocks, tab_futures = st.tabs(["📊 Stock Breakouts", "⛓️ Futures Monitoring"])

with tab_stocks:
    data_rows = []
    breakout_model = st.session_state.get("breakout_model", "v2")
    benchmark_df = None
    if breakout_model == "v2":
        try:
            benchmark_df, _ = get_stock_data("^KLSE", period="1y")
        except Exception:
            benchmark_df = None

    # Use a spinner for the load
    with st.spinner("Fetching latest live prices..."):
        for t in st.session_state.watchlist:
            # Skip futures in the stock tab if they were added manually
            if "=F" in t: continue
            df, name = get_stock_data(t, period="1y")
            if df is not None and not df.empty:
                if breakout_model == "v2":
                    analysis = analyze_breakout_v2(t, df, name, benchmark_df=benchmark_df) or analyze_breakout(t, df, name)
                else:
                    analysis = analyze_breakout(t, df, name)
                if analysis:
                    data_rows.append(analysis)

    if data_rows:
        # Top Metrics
        strong_threshold = 7 if breakout_model == "v2" else 4
        neutral_threshold = 4 if breakout_model == "v2" else 2
        total_breakouts = len([r for r in data_rows if int(r.get('score', 0)) >= strong_threshold])
        avg_rsi = sum([r['rsi'] for r in data_rows]) / len(data_rows)
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Strong Breakouts (Score {strong_threshold}+)", total_breakouts)
        col2.metric("Watchlist Count", len(data_rows))
        col3.metric("Avg Watchlist RSI", f"{avg_rsi:.1f}")

        st.markdown("### 📊 Live Breakout Analysis")
        
        # Prepare display dataframe
        display_rows = []
        for r in data_rows:
            link = f"?chart={quote(r['ticker'])}&popup=1"
            linked_name = f'<a href="{link}" target="_blank" rel="noopener noreferrer">{r["name"]}</a>'
            score_max = int(r.get("score_max", 5))
            score_val = int(r.get("score", 0))
            display_rows.append({
                "Ticker": r['ticker'],
                "Name": linked_name,
                "Last Price (RM)": f"{float(r['price']):.2f}",
                "Score": f"{score_val}/{score_max}",
                "RSI": r['rsi'],
                "Status": "🔥 STRONG" if score_val >= strong_threshold else ("⚖️ NEUTRAL" if score_val >= neutral_threshold else "❄️ WEAK"),
                "Catalyst / Insight": r['catalyst'] if score_val >= neutral_threshold else r['analysis']
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
                "Last Price (RM)": f"{float(r['price']):.2f}",
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
    You can switch between **Stronger (V2)** and **Original (V1)** using the sidebar toggle.
    
    **Stronger (V2) — Score 0-10** emphasizes:
    
    1. **Trend strength (SMA50 & SMA200)**: Price above rising moving averages.
    2. **Breakout trigger (55-day high)**: Close breaks above the prior 55 trading days' close-high.
    3. **Confirmation (volume & liquidity)**: Volume surge and sufficient average traded value.
    4. **Quality (close strength & volatility contraction)**: Strong close within the day's range and tighter volatility before the breakout.
    5. **Leadership (relative strength vs KLCI)**: Outperformance versus the KLCI benchmark over ~3 months.

    **Original (V1) — Score 0-5** emphasizes:
    
    1. **Trend (SMA20 & SMA50)**: Price above both moving averages.
    2. **Volume surge**: Volume > 1.5× 20-day average.
    3. **Breakout**: Close above the prior 20-day close-high.
    
    **Status Legend:**
    * 🔥 **STRONG (Score 7-10)**
    * ⚖️ **NEUTRAL (Score 4-6)**
    * ❄️ **WEAK (Score 0-3)**
    """)
