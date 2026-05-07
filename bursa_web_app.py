import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
root_app = root_dir / "bursa_web_app.py"
if root_app.exists() and root_app.resolve() != Path(__file__).resolve():
    sys.path.insert(0, str(root_dir))
    import runpy

    runpy.run_path(str(root_app), run_name="__main__")
    raise SystemExit

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout, analyze_breakout_v2, analyze_breakout_v3, search_bursa, get_top_breakouts, get_stock_universe, BURSA_UNIVERSE_FILE, KLCI_COMPONENTS, get_futures_breakouts

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
if "sector_focus" not in st.session_state:
    st.session_state.sector_focus = []
if "v3_signal_lookback" not in st.session_state:
    st.session_state.v3_signal_lookback = 5
if "v3_max_runup_pct" not in st.session_state:
    st.session_state.v3_max_runup_pct = None
if "v3_max_pullback_pct" not in st.session_state:
    st.session_state.v3_max_pullback_pct = None
if "v3_retest_days" not in st.session_state:
    st.session_state.v3_retest_days = 0
if "max_tickers_scan" not in st.session_state:
    st.session_state.max_tickers_scan = 300

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
        top_breakouts = get_top_breakouts(
            limit=20,
            model=st.session_state.breakout_model,
            universe_mode=st.session_state.universe_mode,
            sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
            signal_lookback=st.session_state.v3_signal_lookback,
            max_runup_pct=st.session_state.v3_max_runup_pct,
            max_pullback_pct=st.session_state.v3_max_pullback_pct,
            retest_days=st.session_state.v3_retest_days,
            max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
        )
        if top_breakouts:
            st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        else:
            fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
            st.session_state.watchlist = list(fallback_universe[:20])

# Sidebar for adding stocks (hide in popup mode)
if not popup_mode:
    st.sidebar.header("🔍 Market Discovery")
    st.sidebar.info("Scans a Bursa universe to identify the strongest technical breakouts.")
    try:
        import bursa_core as _core
        st.sidebar.caption(f"App: {__file__}")
        st.sidebar.caption(f"Core: {_core.__file__}")
    except Exception:
        pass

    universe_list, universe_src = get_stock_universe(st.session_state.universe_mode)
    st.sidebar.caption(f"Universe loaded: {len(universe_list)} tickers ({universe_src})")
    if universe_src != "file" and st.session_state.universe_mode == "file":
        st.sidebar.warning(f"Could not load {BURSA_UNIVERSE_FILE}. Falling back to curated universe.")

    universe_options = {
        "Focus: Tech + Energy + Banks + Utilities + Infra + Telco (Large/Mid)": "focus",
        "Index: KLCI 30 (Big Cap)": "klci",
        "Index: FBM Mid 70": "fbm70",
        "Index: FBM Top 100": "fbm100",
        "Index: FBM Small Cap": "smallcap",
        "Sector: Tech & Semicon (Large/Mid)": "sector-tech",
        "Sector: Utilities (Large/Mid)": "sector-utilities",
        "Sector: Infrastructure (Large/Mid)": "sector-infra",
        "Sector: Property & REIT (Large/Mid)": "sector-property",
        "Sector: Consumer (Large/Mid)": "sector-consumer",
        "Sector: Banks & Financials (Large/Mid)": "sector-banks",
        "Sector: Healthcare (Large/Mid)": "sector-healthcare",
        "Sector: Energy (Oil & Gas) (Large/Mid)": "sector-energy",
        "Sector: Plantation (Large/Mid)": "sector-plantation",
        "Sector: Telco & Media (Large/Mid)": "sector-telco",
        "Sector: Industrials (Large/Mid)": "sector-industrial",
        "Curated (Fast)": "curated",
        "From File (Full)": "file",
        "Auto (Malaysia)": "auto",
    }
    inv_universe = {v: k for k, v in universe_options.items()}
    current_label = inv_universe.get(st.session_state.universe_mode, "Curated (Fast)")
    universe_label = st.sidebar.selectbox("Universe", list(universe_options.keys()), index=list(universe_options.keys()).index(current_label))
    selected_universe = universe_options.get(universe_label, "curated")
    if selected_universe != st.session_state.universe_mode:
        st.session_state.universe_mode = selected_universe
        with st.spinner("Refreshing list for selected universe..."):
            top_breakouts = get_top_breakouts(
                limit=20,
                model=st.session_state.breakout_model,
                universe_mode=st.session_state.universe_mode,
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
            )
            if top_breakouts:
                st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
            else:
                st.session_state.watchlist = list(universe_list[:20])
        st.rerun()

    if st.session_state.universe_mode in {"klci", "fbm70", "fbm100", "smallcap"} or str(st.session_state.universe_mode).startswith("sector-"):
        if "klci_auto_update" not in st.session_state:
            st.session_state.klci_auto_update = True
        if "index_force_refresh" not in st.session_state:
            st.session_state.index_force_refresh = False
        try:
            import bursa_core as _core
            st.session_state.klci_auto_update = st.sidebar.checkbox("Auto-update index constituents", value=bool(st.session_state.klci_auto_update))
            st.session_state.index_force_refresh = st.sidebar.checkbox(
                "Force refresh (no cache)",
                value=bool(st.session_state.index_force_refresh),
                help="When enabled, index constituents are fetched from the source each run (slower).",
            )
            _core.KLCI_AUTO_UPDATE_ENABLED = bool(st.session_state.klci_auto_update)
            _core.INDEX_AUTO_UPDATE_ENABLED = bool(st.session_state.klci_auto_update)
            _core.INDEX_FORCE_REFRESH = bool(st.session_state.index_force_refresh)

            if st.session_state.universe_mode == "klci":
                info = _core.get_klci_components_info(max_age_days=30)
                src = str(info.get("source") or "")
                updated_at = info.get("updated_at")
                if updated_at:
                    st.sidebar.caption(f"KLCI list: {src}, updated {updated_at}")
                else:
                    st.sidebar.caption(f"KLCI list: {src}")
                update_label = "Update KLCI Now"
            elif st.session_state.universe_mode in {"fbm70", "fbm100", "smallcap"}:
                update_label = "Update Index Now"
                info = _core.get_index_components_info(st.session_state.universe_mode, max_age_days=30)
                src = str(info.get("source") or "")
                updated_at = info.get("updated_at")
                if updated_at:
                    st.sidebar.caption(f"Index list: {src}, updated {updated_at}")
                else:
                    st.sidebar.caption(f"Index list: {src}")
            else:
                update_label = "Update Large/Mid Lists Now"
                info_klci = _core.get_klci_components_info(max_age_days=30)
                info_70 = _core.get_index_components_info("fbm70", max_age_days=30)
                info_100 = _core.get_index_components_info("fbm100", max_age_days=30)
                st.sidebar.caption(f"KLCI: {info_klci.get('source')}, {info_klci.get('updated_at') or 'n/a'}")
                st.sidebar.caption(f"FBM70: {info_70.get('source')}, {info_70.get('updated_at') or 'n/a'}")
                st.sidebar.caption(f"FBM100: {info_100.get('source')}, {info_100.get('updated_at') or 'n/a'}")

            if st.sidebar.button(update_label, use_container_width=True):
                with st.spinner("Updating constituents..."):
                    if st.session_state.universe_mode == "klci":
                        _core.refresh_klci_components(force=True, max_age_days=30)
                    elif st.session_state.universe_mode in {"fbm70", "fbm100", "smallcap"}:
                        _core.refresh_index_components(st.session_state.universe_mode, force=True, max_age_days=30)
                    else:
                        _core.refresh_klci_components(force=True, max_age_days=30)
                        _core.refresh_index_components("fbm70", force=True, max_age_days=30)
                        _core.refresh_index_components("fbm100", force=True, max_age_days=30)
                    top_breakouts = get_top_breakouts(
                        limit=20,
                        model=st.session_state.breakout_model,
                        universe_mode=st.session_state.universe_mode,
                        sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                        signal_lookback=st.session_state.v3_signal_lookback,
                        max_runup_pct=st.session_state.v3_max_runup_pct,
                        max_pullback_pct=st.session_state.v3_max_pullback_pct,
                        retest_days=st.session_state.v3_retest_days,
                    )
                    st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
                st.rerun()
        except Exception:
            pass

    if st.session_state.universe_mode == "auto":
        st.sidebar.caption("Auto universe downloads & caches a Malaysia stock list; the first run may take longer.")
        max_scan = st.sidebar.slider("Max tickers to scan", min_value=50, max_value=1200, value=int(st.session_state.max_tickers_scan), step=50)
        if int(max_scan) != int(st.session_state.max_tickers_scan):
            st.session_state.max_tickers_scan = int(max_scan)
            with st.spinner("Refreshing list for scan size..."):
                top_breakouts = get_top_breakouts(
                    limit=20,
                    model=st.session_state.breakout_model,
                    universe_mode=st.session_state.universe_mode,
                    sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                    signal_lookback=st.session_state.v3_signal_lookback,
                    max_runup_pct=st.session_state.v3_max_runup_pct,
                    max_pullback_pct=st.session_state.v3_max_pullback_pct,
                    retest_days=st.session_state.v3_retest_days,
                    max_tickers=st.session_state.max_tickers_scan,
                )
                if top_breakouts:
                    st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
                else:
                    fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                    st.session_state.watchlist = list(fallback_universe[:20])
            st.rerun()
    if st.session_state.universe_mode == "file":
        st.sidebar.caption("Universe source: bursa_universe.csv in the app folder. Put one 4-digit stock code per line (Main + ACE). Example: 6742 or 6742.KL.")

    model_label = st.sidebar.radio(
        "Breakout Model",
        ["Breakout Candle (V3)", "Stronger (V2)", "Original (V1)"],
        index=0 if st.session_state.breakout_model == "v3" else (1 if st.session_state.breakout_model == "v2" else 2),
        horizontal=True,
    )
    selected_model = "v3" if model_label.startswith("Breakout") else ("v2" if model_label.startswith("Stronger") else "v1")
    if selected_model != st.session_state.breakout_model:
        st.session_state.breakout_model = selected_model
        with st.spinner("Refreshing list for selected model..."):
            top_breakouts = get_top_breakouts(
                limit=20,
                model=st.session_state.breakout_model,
                universe_mode=st.session_state.universe_mode,
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
            )
            if top_breakouts:
                st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                st.session_state.watchlist = list(fallback_universe[:20])
        st.rerun()


    if st.session_state.breakout_model == "v3":
        if "v3_entry_style" not in st.session_state:
            st.session_state.v3_entry_style = "Early Entry"
        if "v3_signal_filter" not in st.session_state:
            st.session_state.v3_signal_filter = "all"

        entry_options = [
            "Early Entry (Recommended)",
            "Balanced",
            "Confirmed",
            "Late (Chasing Risk)",
            "Failed (Breakout Broke)",
            "Custom (Manual)",
        ]
        entry_idx = 0
        if str(st.session_state.v3_entry_style).startswith("Balanced"):
            entry_idx = 1
        elif str(st.session_state.v3_entry_style).startswith("Confirmed"):
            entry_idx = 2
        elif str(st.session_state.v3_entry_style).startswith("Late"):
            entry_idx = 3
        elif str(st.session_state.v3_entry_style).startswith("Failed"):
            entry_idx = 4
        elif str(st.session_state.v3_entry_style).startswith("Custom"):
            entry_idx = 5

        entry_label = st.sidebar.selectbox("Entry Style", entry_options, index=entry_idx)
        if entry_label.startswith("Early"):
            selected_style = "Early Entry"
        elif entry_label.startswith("Balanced"):
            selected_style = "Balanced"
        elif entry_label.startswith("Confirmed"):
            selected_style = "Confirmed"
        elif entry_label.startswith("Late"):
            selected_style = "Late"
        elif entry_label.startswith("Failed"):
            selected_style = "Failed"
        else:
            selected_style = "Custom"

        if selected_style != st.session_state.v3_entry_style:
            st.session_state.v3_entry_style = selected_style

            if selected_style == "Early Entry":
                st.session_state.v3_signal_filter = "all"
                st.session_state.v3_signal_lookback = 5
                st.session_state.v3_max_runup_pct = 5.0
                st.session_state.v3_max_pullback_pct = 2.0
                st.session_state.v3_retest_days = 0
            elif selected_style == "Balanced":
                st.session_state.v3_signal_filter = "all"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = 8.0
                st.session_state.v3_max_pullback_pct = 3.0
                st.session_state.v3_retest_days = 3
            elif selected_style == "Confirmed":
                st.session_state.v3_signal_filter = "all"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = None
                st.session_state.v3_max_pullback_pct = 3.0
                st.session_state.v3_retest_days = 5
            elif selected_style == "Late":
                st.session_state.v3_signal_filter = "late"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = 5.0
                st.session_state.v3_max_pullback_pct = 2.0
                st.session_state.v3_retest_days = 0
            else:
                if selected_style == "Failed":
                    st.session_state.v3_signal_filter = "failed"
                    st.session_state.v3_signal_lookback = 10
                    st.session_state.v3_max_runup_pct = None
                    st.session_state.v3_max_pullback_pct = 2.0
                    st.session_state.v3_retest_days = 0

            with st.spinner("Applying entry style..."):
                scan_limit = 9999 if st.session_state.v3_signal_filter in {"late", "failed"} else 20
                top_breakouts = get_top_breakouts(
                    limit=scan_limit,
                    model=st.session_state.breakout_model,
                    universe_mode=st.session_state.universe_mode,
                    sector_allowlist=st.session_state.sector_focus or None,
                    signal_lookback=st.session_state.v3_signal_lookback,
                    max_runup_pct=st.session_state.v3_max_runup_pct,
                    max_pullback_pct=st.session_state.v3_max_pullback_pct,
                    retest_days=st.session_state.v3_retest_days,
                    max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
                )
                if st.session_state.v3_signal_filter in {"late", "failed"}:
                    filtered = []
                    for r in top_breakouts:
                        is_confirmed = bool(r.get("retest_confirmed"))
                        is_breakout = bool(r.get("breakout_candle_valid"))
                        is_failed = bool(r.get("breakout_candle")) and (r.get("breakout_hold_ok") is False)
                        is_late = bool(r.get("breakout_candle")) and (not is_breakout) and (not is_confirmed) and (not is_failed)
                        if st.session_state.v3_signal_filter == "late" and is_late:
                            filtered.append(r)
                        elif st.session_state.v3_signal_filter == "failed" and is_failed:
                            filtered.append(r)
                    if filtered:
                        st.session_state.watchlist = [res['ticker'] for res in filtered[:20]]
                        st.session_state.v3_filter_note = None
                    else:
                        st.session_state.v3_filter_note = "No matching Late/Failed signals found in the scanned universe. Showing the default list instead."
                        if top_breakouts:
                            st.session_state.watchlist = [res['ticker'] for res in top_breakouts[:20]]
                        else:
                            fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                            st.session_state.watchlist = list(fallback_universe[:20])
                else:
                    st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
                    st.session_state.v3_filter_note = None
            st.rerun()


        st.sidebar.caption(
            f"V3 rules: {int(st.session_state.v3_signal_lookback)}d window, "
            f"run-up {'Off' if st.session_state.v3_max_runup_pct is None else str(st.session_state.v3_max_runup_pct) + '%'}, "
            f"pullback {'Off' if st.session_state.v3_max_pullback_pct is None else str(st.session_state.v3_max_pullback_pct) + '%'}, "
            f"retest {'Off' if int(st.session_state.v3_retest_days) == 0 else str(int(st.session_state.v3_retest_days)) + 'd'}"
        )

        st.sidebar.caption("Note: V3 is stricter than V1/V2. A stock can rank high in V1 but show no V3 signal if it lacks a recent power-candle + volume breakout.")

        if "v3_breakout_day_only" not in st.session_state:
            st.session_state.v3_breakout_day_only = False
        if "v3_filter_note" not in st.session_state:
            st.session_state.v3_filter_note = None
        st.session_state.v3_breakout_day_only = st.sidebar.toggle(
            "Breakout-day entry only",
            value=bool(st.session_state.v3_breakout_day_only),
            help="Shows only ⚡ BREAKOUT signals with run-up within the current V3 Max Run-up setting.",
        )

        with st.sidebar.expander("Advanced V3 Filters", expanded=False):
            prev_adv = (
                int(st.session_state.v3_signal_lookback),
                st.session_state.v3_max_runup_pct,
                st.session_state.v3_max_pullback_pct,
                int(st.session_state.v3_retest_days),
            )

            st.radio(
                "V3 Breakout Window",
                [3, 5, 10],
                index=1 if int(st.session_state.v3_signal_lookback) == 5 else (0 if int(st.session_state.v3_signal_lookback) == 3 else 2),
                horizontal=True,
                key="v3_signal_lookback",
            )

            st.radio(
                "V3 Max Run-up",
                [None, 3.0, 5.0, 8.0],
                index=0 if st.session_state.v3_max_runup_pct is None else (1 if float(st.session_state.v3_max_runup_pct) == 3.0 else (2 if float(st.session_state.v3_max_runup_pct) == 5.0 else 3)),
                format_func=lambda x: "Off" if x is None else f"{int(x)}%",
                horizontal=True,
                key="v3_max_runup_pct",
            )

            st.radio(
                "V3 Max Pullback",
                [None, 0.0, 2.0, 3.0],
                index=0 if st.session_state.v3_max_pullback_pct is None else (1 if float(st.session_state.v3_max_pullback_pct) == 0.0 else (2 if float(st.session_state.v3_max_pullback_pct) == 2.0 else 3)),
                format_func=lambda x: "Off" if x is None else f"{int(x)}%",
                horizontal=True,
                key="v3_max_pullback_pct",
            )

            st.radio(
                "V3 Retest Confirm",
                [0, 3, 5],
                index=0 if int(st.session_state.v3_retest_days) == 0 else (1 if int(st.session_state.v3_retest_days) == 3 else 2),
                format_func=lambda x: "Off" if int(x) == 0 else f"{int(x)}d",
                horizontal=True,
                key="v3_retest_days",
            )

            new_adv = (
                int(st.session_state.v3_signal_lookback),
                st.session_state.v3_max_runup_pct,
                st.session_state.v3_max_pullback_pct,
                int(st.session_state.v3_retest_days),
            )
            if new_adv != prev_adv:
                st.session_state.v3_entry_style = "Custom"
                with st.spinner("Refreshing list..."):
                    top_breakouts = get_top_breakouts(
                        limit=20,
                        model=st.session_state.breakout_model,
                        universe_mode=st.session_state.universe_mode,
                        sector_allowlist=st.session_state.sector_focus or None,
                        signal_lookback=st.session_state.v3_signal_lookback,
                        max_runup_pct=st.session_state.v3_max_runup_pct,
                        max_pullback_pct=st.session_state.v3_max_pullback_pct,
                        retest_days=st.session_state.v3_retest_days,
                        max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
                    )
                    st.session_state.watchlist = [res['ticker'] for res in top_breakouts]

    sectors = sorted({str(v.get("sector")).strip() for v in MARKET_INSIGHTS.values() if str(v.get("sector") or "").strip()})
    if sectors:
        selected_sectors = st.sidebar.multiselect(
            "Sector Focus (optional)",
            options=sectors,
            default=st.session_state.sector_focus,
        )
        if selected_sectors != st.session_state.sector_focus:
            st.session_state.sector_focus = selected_sectors
            with st.spinner("Refreshing list for selected sector focus..."):
                top_breakouts = get_top_breakouts(
                    limit=20,
                    model=st.session_state.breakout_model,
                    universe_mode=st.session_state.universe_mode,
                    sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                    signal_lookback=st.session_state.v3_signal_lookback,
                    max_runup_pct=st.session_state.v3_max_runup_pct,
                    max_pullback_pct=st.session_state.v3_max_pullback_pct,
                    retest_days=st.session_state.v3_retest_days,
                    max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
                )
                st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
            st.rerun()

    if st.sidebar.button("🔄 Refresh Market Discovery", use_container_width=True):
        with st.spinner("Re-scanning KLCI components..."):
            top_breakouts = get_top_breakouts(
                limit=20,
                model=st.session_state.breakout_model,
                universe_mode=st.session_state.universe_mode,
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
            )
            if top_breakouts:
                st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                st.session_state.watchlist = list(fallback_universe[:20])
            st.success("Dashboard updated!")
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("📡 Data")
    if "price_data_mode" not in st.session_state:
        st.session_state.price_data_mode = "fast"
    if "tv_price_overlay" not in st.session_state:
        st.session_state.tv_price_overlay = False
    try:
        import bursa_core as _core
        mode_label = st.sidebar.selectbox(
            "Price Data",
            ["Fast (cache 15 min)", "Latest (no cache)", "Offline (cache only)"],
            index=0 if st.session_state.price_data_mode == "fast" else (1 if st.session_state.price_data_mode == "latest" else 2),
            help="Fast reduces rate limits by caching recent OHLCV; Latest always re-fetches; Offline uses last cached candles.",
        )
        st.session_state.price_data_mode = "fast" if mode_label.startswith("Fast") else ("latest" if mode_label.startswith("Latest") else "offline")
        _core.PRICE_CACHE_MODE = st.session_state.price_data_mode
        _core.PRICE_CACHE_MAX_AGE_SECONDS = 15 * 60

        st.session_state.tv_price_overlay = st.sidebar.checkbox(
            "Overlay TradingView last price",
            value=bool(st.session_state.tv_price_overlay),
            help="Replaces the latest Close with TradingView last price (MYX-####). Uses a short cache to reduce requests.",
        )
        _core.TRADINGVIEW_PRICE_OVERLAY_ENABLED = bool(st.session_state.tv_price_overlay)
    except Exception:
        pass

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
        top_breakouts = get_top_breakouts(
            limit=20,
            model=st.session_state.breakout_model,
            universe_mode=st.session_state.universe_mode,
            sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model == "v3" else None,
            signal_lookback=st.session_state.v3_signal_lookback,
            max_runup_pct=st.session_state.v3_max_runup_pct,
            max_pullback_pct=st.session_state.v3_max_pullback_pct,
            retest_days=st.session_state.v3_retest_days,
            max_tickers=st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None,
        )
        st.session_state.watchlist = [res['ticker'] for res in top_breakouts]
        st.rerun()

# --- MAIN DASHBOARD TABS ---
tab_stocks, tab_futures = st.tabs(["📊 Stock Breakouts", "⛓️ Futures Monitoring"])

with tab_stocks:
    data_rows = []
    fetch_attempted = 0
    fetch_success = 0
    breakout_model = st.session_state.get("breakout_model", "v2")
    benchmark_df = None
    if breakout_model in {"v2", "v3"}:
        try:
            benchmark_df, _ = get_stock_data("^KLSE", period="1y")
        except Exception:
            benchmark_df = None

    # Use a spinner for the load
    with st.spinner("Fetching latest live prices..."):
        for t in st.session_state.watchlist:
            # Skip futures in the stock tab if they were added manually
            if "=F" in t: continue
            fetch_attempted += 1
            df, name = get_stock_data(t, period="1y")
            if df is not None and not df.empty:
                fetch_success += 1
                if breakout_model == "v3":
                    analysis = analyze_breakout_v3(
                        t,
                        df,
                        name,
                        benchmark_df=benchmark_df,
                        min_rows=min(120, len(df)),
                        signal_lookback=st.session_state.v3_signal_lookback,
                        max_runup_pct=st.session_state.v3_max_runup_pct,
                        max_pullback_pct=st.session_state.v3_max_pullback_pct,
                        retest_days=st.session_state.v3_retest_days,
                    )
                elif breakout_model == "v2":
                    analysis = analyze_breakout_v2(t, df, name, benchmark_df=benchmark_df, min_rows=min(120, len(df)))
                else:
                    analysis = analyze_breakout(t, df, name)
                if analysis:
                    data_rows.append(analysis)

    if data_rows:
        if breakout_model == "v3" and st.session_state.get("v3_filter_note"):
            st.info(str(st.session_state.get("v3_filter_note")))

        if breakout_model == "v3":
            sig_filter = str(st.session_state.get("v3_signal_filter", "all") or "all").lower().strip()
            original_rows = list(data_rows)
            filtered = data_rows
            if sig_filter in {"late", "failed"}:
                tmp = []
                for r in filtered:
                    is_confirmed = bool(r.get("retest_confirmed"))
                    is_breakout = bool(r.get("breakout_candle_valid"))
                    is_failed = bool(r.get("breakout_candle")) and (r.get("breakout_hold_ok") is False)
                    is_late = bool(r.get("breakout_candle")) and (not is_breakout) and (not is_confirmed) and (not is_failed)
                    if sig_filter == "late" and is_late:
                        tmp.append(r)
                    elif sig_filter == "failed" and is_failed:
                        tmp.append(r)
                filtered = tmp

            if bool(st.session_state.get("v3_breakout_day_only")):
                tmp = []
                for r in filtered:
                    if not bool(r.get("breakout_candle_valid")):
                        continue
                    if r.get("runup_pct") is None:
                        continue
                    max_runup = st.session_state.get("v3_max_runup_pct")
                    if max_runup is not None and float(r.get("runup_pct")) > float(max_runup):
                        continue
                    tmp.append(r)
                filtered = tmp

            if not filtered:
                st.warning("No matching rows for the selected V3 filter. Showing the full list instead.")
                data_rows = original_rows
            else:
                data_rows = filtered

        if not data_rows:
            st.warning("No matching signals for the selected Entry Style. Try a different universe or style.")
            st.stop()

        # Top Metrics
        if breakout_model == "v3":
            strong_threshold = 8
            neutral_threshold = 5
            total_breakouts = len([r for r in data_rows if bool(r.get("retest_confirmed")) or bool(r.get("breakout_candle_valid"))])
            metric_label = "Valid V3 Signals"
        elif breakout_model == "v2":
            strong_threshold = 7
            neutral_threshold = 4
            total_breakouts = len([r for r in data_rows if int(r.get('score', 0)) >= strong_threshold])
            metric_label = f"Strong Breakouts (Score {strong_threshold}+)"
        else:
            strong_threshold = 4
            neutral_threshold = 2
            total_breakouts = len([r for r in data_rows if int(r.get('score', 0)) >= strong_threshold])
            metric_label = f"Strong Breakouts (Score {strong_threshold}+)"

        avg_rsi = sum([r['rsi'] for r in data_rows]) / max(1, len(data_rows))
        
        col1, col2, col3 = st.columns(3)
        col1.metric(metric_label, total_breakouts)
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

            if breakout_model == "v3":
                if r.get("retest_confirmed"):
                    status = "🔥 STRONG"
                elif r.get("breakout_candle_valid"):
                    status = "🔥 STRONG"
                elif r.get("breakout_55"):
                    status = "⚖️ NEUTRAL"
                else:
                    status = "⚖️ NEUTRAL" if score_val >= neutral_threshold else "❄️ WEAK"
            else:
                status = "🔥 STRONG" if score_val >= strong_threshold else ("⚖️ NEUTRAL" if score_val >= neutral_threshold else "❄️ WEAK")

            display_rows.append({
                "Ticker": r['ticker'],
                "Name": linked_name,
                "Sector": r.get("sector", ""),
                "Last Price (RM)": f"{float(r['price']):.2f}",
                "Score": f"{score_val}/{score_max}",
                "RSI": r['rsi'],
                "Signal": "✅ CONFIRMED" if r.get("retest_confirmed") else ("⚡ BREAKOUT" if r.get("breakout_candle_valid") else ("❌ FAILED" if (r.get("breakout_candle") and (r.get("breakout_hold_ok") is False)) else ("⏰ LATE" if r.get("breakout_candle") else ("📈 Breakout" if r.get("breakout_55") else "")))),
                "Signal Date": r.get("breakout_candle_date", ""),
                "Retest": "✅" if r.get("retest_confirmed") else ("⏳" if (int(r.get("retest_days") or 0) > 0 and r.get("breakout_candle_valid")) else ""),
                "Retest Date": r.get("retest_touch_date", ""),
                "Run-up %": "" if r.get("runup_pct") is None else f"{float(r.get('runup_pct')):.1f}%",
                "Status": status,
                "Catalyst / Insight": r['catalyst'] if score_val >= neutral_threshold else r['analysis']
            })
        
        df_display = pd.DataFrame(display_rows)
        st.caption("Tip: click the stock name to open its chart in a new window/tab.")
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.warning("No data found. Please click 'Refresh Market Discovery' or add valid tickers.")
        st.caption(f"Fetch summary: {fetch_success}/{fetch_attempted} tickers returned data.")
        if fetch_attempted == 0:
            st.caption("Watchlist is empty. Try switching universe, clicking 'Refresh Market Discovery', or 'Reset to Top 20'.")
        st.caption("If this stays 0, Yahoo data may be blocked/rate-limited in your environment. Try again later, reduce scan size, or switch to a smaller universe (KLCI/Top100).")
        st.caption("Optional fallback: set BURSA_PRICE_API_BASE_URL and BURSA_PRICE_API_KEY in your environment to use a non-Yahoo data source.")

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
    You can switch between **Breakout Candle (V3)**, **Stronger (V2)** and **Original (V1)** using the sidebar toggle.
    
    **Breakout Candle (V3) — Score 0-11** keeps the V2 foundation, and adds a bonus when the latest bar is a breakout candle:
    
    - **Breakout candle** = 55-day breakout + bullish power candle + volume spike
    
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
