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
import time
import os
import hashlib
import hmac
import base64
import json
from urllib.parse import quote
from html import escape as _html_escape
import streamlit.components.v1 as components
import bursa_core as _core

MARKET_INSIGHTS = _core.MARKET_INSIGHTS
get_stock_data = _core.get_stock_data
analyze_breakout = _core.analyze_breakout
analyze_breakout_v2 = _core.analyze_breakout_v2
analyze_breakout_v3 = _core.analyze_breakout_v3
analyze_breakout_v3_quote = getattr(_core, "analyze_breakout_v3_quote", None)
search_bursa = _core.search_bursa
get_top_breakouts = _core.get_top_breakouts
get_stock_universe = _core.get_stock_universe
BURSA_UNIVERSE_FILE = _core.BURSA_UNIVERSE_FILE
KLCI_COMPONENTS = _core.KLCI_COMPONENTS
get_futures_breakouts = _core.get_futures_breakouts

# --- PAGE CONFIG ---
st.set_page_config(page_title="Bursa Breakout Analyzer", layout="wide", page_icon="📈")

def _get_secret_value(key: str) -> str | None:
    try:
        v = None
        try:
            v = st.secrets.get(key)
        except Exception:
            try:
                v = st.secrets[key]
            except Exception:
                v = None
        if v is None:
            v = os.environ.get(key)
        if v is None:
            return None
        s = str(v)
        return s
    except Exception:
        return None


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()


def _auth_secret() -> str:
    v = _get_secret_value("APP_AUTH_SECRET")
    if v:
        return str(v)
    v = _get_secret_value("APP_PASSWORD")
    if v:
        return str(v)
    v = _get_secret_value("APP_PASSWORD_SHA256")
    if v:
        return str(v)
    v = _get_secret_value("APP_USERNAME")
    if v:
        return str(v)
    return "change-me"


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s or "") + pad)


def _make_auth_token(username: str, ttl_seconds: int = 12 * 3600) -> str:
    payload = {"u": str(username or "").strip(), "exp": int(time.time()) + int(ttl_seconds)}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    p = _b64url_encode(raw)
    sig = hmac.new(_auth_secret().encode("utf-8"), p.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{p}.{sig}"


def _verify_auth_token(token: str) -> str | None:
    try:
        t = str(token or "").strip()
        if not t or "." not in t:
            return None
        p, sig = t.split(".", 1)
        expected = hmac.new(_auth_secret().encode("utf-8"), p.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(sig), str(expected)):
            return None
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        exp = int(payload.get("exp") or 0)
        if exp <= int(time.time()):
            return None
        u = str(payload.get("u") or "").strip()
        return u if u else None
    except Exception:
        return None


def _strip_auth_from_url() -> None:
    try:
        components.html(
            """
<script>
(function () {
  try {
    const url = new URL(window.location.href);
    if (!url.searchParams.has('auth')) return;
    url.searchParams.delete('auth');
    window.history.replaceState({}, '', url.toString());
  } catch (e) {}
})();
</script>
""",
            height=0,
        )
    except Exception:
        pass


def _set_query_params(**kwargs) -> None:
    try:
        qp = {}
        for k, v in kwargs.items():
            if v is None:
                continue
            qp[str(k)] = str(v)
        try:
            st.query_params.clear()
            for k, v in qp.items():
                st.query_params[k] = v
        except Exception:
            st.experimental_set_query_params(**qp)
    except Exception:
        return


def _clear_query_params() -> None:
    try:
        try:
            st.query_params.clear()
        except Exception:
            st.experimental_set_query_params()
    except Exception:
        return


def _require_login(popup_mode: bool) -> None:
    expected_user = _get_secret_value("APP_USERNAME")
    expected_pw = _get_secret_value("APP_PASSWORD")
    expected_pw_sha = _get_secret_value("APP_PASSWORD_SHA256")

    if not expected_user or (not expected_pw and not expected_pw_sha):
        st.error("Login is enabled but credentials are not configured. Set APP_USERNAME and either APP_PASSWORD or APP_PASSWORD_SHA256 in Streamlit Secrets / environment variables.")
        st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        u_from_token = _verify_auth_token(_get_query_param("auth"))
        if u_from_token:
            st.session_state.authenticated = True
            st.session_state.auth_user = u_from_token
            st.session_state.auth_token = str(_get_query_param("auth") or "").strip()
            _strip_auth_from_url()

    if st.session_state.authenticated:
        if not popup_mode:
            try:
                with st.sidebar:
                    if st.button("Logout", use_container_width=True):
                        st.session_state.authenticated = False
                        st.session_state.auth_user = None
                        st.session_state.auth_token = None
                        st.rerun()
            except Exception:
                pass
        return

    st.title("🔐 Login")
    st.caption("Enter your username and password to continue.")
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        ok_user = hmac.compare_digest(str(u or ""), str(expected_user or ""))
        if expected_pw_sha:
            ok_pw = hmac.compare_digest(_sha256_hex(p or ""), str(expected_pw_sha or "").strip().lower())
        else:
            ok_pw = hmac.compare_digest(str(p or ""), str(expected_pw or ""))
        if ok_user and ok_pw:
            st.session_state.authenticated = True
            st.session_state.auth_user = str(u or "").strip()
            tok = _make_auth_token(st.session_state.auth_user, ttl_seconds=12 * 3600)
            st.session_state.auth_token = tok
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

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

    try:
        if hasattr(_core, "_resolve_insight_v3"):
            _, nm, *_ = _core._resolve_insight_v3(symbol, name_chart)
            if nm:
                name_chart = nm
    except Exception:
        pass

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

_require_login(bool(popup_mode))

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

def _notify(kind: str, text: str) -> None:
    k = str(kind or "info").lower().strip()
    t = str(text or "")
    if not t:
        return
    if hasattr(st, "toast"):
        try:
            icon = "✅" if k == "success" else ("❌" if k == "error" else ("⚠️" if k == "warning" else "ℹ️"))
            st.toast(t, icon=icon)
            return
        except Exception:
            pass
    if k == "success":
        st.success(t)
    elif k == "error":
        st.error(t)
    elif k == "warning":
        st.warning(t)
    else:
        st.info(t)

# Popup/new-tab chart view
if chart_symbol:
    display_name = None
    try:
        if hasattr(_core, "_resolve_insight_v3"):
            _, nm, *_ = _core._resolve_insight_v3(chart_symbol, None)
            if nm:
                display_name = str(nm).strip()
    except Exception:
        display_name = None

    if display_name and display_name.upper() not in {str(chart_symbol).upper().strip(), str(chart_symbol).split(".")[0].upper().strip()}:
        header = f"### {display_name} ({chart_symbol}) — Chart"
    else:
        header = f"### {chart_symbol} — Chart"
    st.markdown(
        header,
    )
    st.caption("This is an in-app chart view.")
    st.caption("Tip: add/remove watchlist items from the main dashboard tab (not the chart tab).")
    with st.spinner(f"Loading chart for {chart_symbol}..."):
        _render_chart(chart_symbol)
    try:
        tok = st.session_state.get("auth_token")
    except Exception:
        tok = None
    if tok:
        st.markdown(f"[Back to Dashboard](/?auth={quote(str(tok))})")
    else:
        st.markdown("[Back to Dashboard](/)")
    st.stop()

def _uniq_tickers(seq):
    seen = set()
    out = []
    for x in (seq or []):
        s = str(x or "").upper().strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


if "manual_watchlist" not in st.session_state:
    st.session_state.manual_watchlist = []


def _apply_watchlist(scanned=None):
    manual = _uniq_tickers(st.session_state.get("manual_watchlist") or [])
    scan = _uniq_tickers(scanned or [])
    st.session_state.manual_watchlist = manual
    st.session_state.watchlist = _uniq_tickers(manual + scan)


# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    with st.spinner("Initializing Market Discovery..."):
        top_breakouts = get_top_breakouts(
            limit=20,
            model=st.session_state.breakout_model,
            universe_mode=st.session_state.universe_mode,
            sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
            signal_lookback=st.session_state.v3_signal_lookback,
            max_runup_pct=st.session_state.v3_max_runup_pct,
            max_pullback_pct=st.session_state.v3_max_pullback_pct,
            retest_days=st.session_state.v3_retest_days,
            max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
        )
        if top_breakouts:
            _apply_watchlist([res['ticker'] for res in top_breakouts])
        else:
            fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
            _apply_watchlist(list(fallback_universe[:20]))

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
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
            )
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                _apply_watchlist(list(universe_list[:20]))
        st.rerun()

    if st.session_state.universe_mode in {"klci", "fbm70", "fbm100", "smallcap"} or str(st.session_state.universe_mode).startswith("sector-"):
        if "klci_auto_update" not in st.session_state:
            st.session_state.klci_auto_update = True
        if "index_force_refresh" not in st.session_state:
            st.session_state.index_force_refresh = False
        try:
            import bursa_core as _core
            st.session_state.klci_auto_update = st.sidebar.checkbox("Auto-update index constituents", value=bool(st.session_state.klci_auto_update))
            if not bool(st.session_state.klci_auto_update) and bool(st.session_state.index_force_refresh):
                st.session_state.index_force_refresh = False
            st.session_state.index_force_refresh = st.sidebar.checkbox(
                "Force refresh index list (no cache)",
                value=bool(st.session_state.index_force_refresh),
                disabled=not bool(st.session_state.klci_auto_update),
                help="Bypasses cached index constituents and fetches from the source each run (slower). If the source is blocked, the app falls back to the last cached list.",
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
                        sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                        signal_lookback=st.session_state.v3_signal_lookback,
                        max_runup_pct=st.session_state.v3_max_runup_pct,
                        max_pullback_pct=st.session_state.v3_max_pullback_pct,
                        retest_days=st.session_state.v3_retest_days,
                    )
                    _apply_watchlist([res['ticker'] for res in top_breakouts])
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
                    sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                    signal_lookback=st.session_state.v3_signal_lookback,
                    max_runup_pct=st.session_state.v3_max_runup_pct,
                    max_pullback_pct=st.session_state.v3_max_pullback_pct,
                    retest_days=st.session_state.v3_retest_days,
                    max_tickers=st.session_state.max_tickers_scan,
                )
                if top_breakouts:
                    _apply_watchlist([res['ticker'] for res in top_breakouts])
                else:
                    fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                    _apply_watchlist(list(fallback_universe[:20]))
            st.rerun()
    if st.session_state.universe_mode == "file":
        st.sidebar.caption("Universe source: bursa_universe.csv in the app folder. Put one 4-digit stock code per line (Main + ACE). Example: 6742 or 6742.KL.")

    model_label = st.sidebar.radio(
        "Breakout Model",
        ["Breakout Candle (V3)", "Intraday (No Token) (V3tv)", "Stronger (V2)", "Original (V1)"],
        index=0 if st.session_state.breakout_model == "v3" else (1 if st.session_state.breakout_model == "v3tv" else (2 if st.session_state.breakout_model == "v2" else 3)),
        horizontal=True,
    )
    if model_label.startswith("Intraday (No Token)"):
        selected_model = "v3tv"
    else:
        selected_model = "v3" if model_label.startswith("Breakout") else ("v2" if model_label.startswith("Stronger") else "v1")
    if selected_model != st.session_state.breakout_model:
        st.session_state.breakout_model = selected_model
        with st.spinner("Refreshing list for selected model..."):
            top_breakouts = get_top_breakouts(
                limit=20,
                model=st.session_state.breakout_model,
                universe_mode=st.session_state.universe_mode,
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
            )
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[:20]))
        st.rerun()

    if st.session_state.breakout_model == "v3tv":
        if "intraday_max_tickers" not in st.session_state:
            st.session_state.intraday_max_tickers = 50
        st.session_state.intraday_max_tickers = st.sidebar.slider(
            "Intraday max tickers",
            min_value=10,
            max_value=200,
            value=int(st.session_state.intraday_max_tickers),
            step=10,
            help="V3tv uses TradingView last price (no token). Keep this smaller to reduce rate limits.",
        )
        st.sidebar.caption("V3tv uses TradingView last price (no token). Results depend on TradingView availability in your environment.")


    if st.session_state.breakout_model in {"v3", "v3tv"}:
        if "v3_entry_style" not in st.session_state:
            st.session_state.v3_entry_style = "Early Entry"
        if "v3_signal_filter" not in st.session_state:
            st.session_state.v3_signal_filter = "all"
        if "v3_show_watchlist_all" not in st.session_state:
            st.session_state.v3_show_watchlist_all = True

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
                if st.session_state.breakout_model == "v3tv":
                    scan_limit = 20
                else:
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
                    max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
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
                        _apply_watchlist([res['ticker'] for res in filtered[:20]])
                        st.session_state.v3_filter_note = None
                    else:
                        st.session_state.v3_filter_note = "No matching Late/Failed signals found in the scanned universe. Showing the default list instead."
                        if top_breakouts:
                            _apply_watchlist([res['ticker'] for res in top_breakouts[:20]])
                        else:
                            fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                            _apply_watchlist(list(fallback_universe[:20]))
                else:
                    _apply_watchlist([res['ticker'] for res in top_breakouts])
                    st.session_state.v3_filter_note = None
            st.rerun()


        st.sidebar.caption(
            f"V3 rules: {int(st.session_state.v3_signal_lookback)}d window, "
            f"run-up {'Off' if st.session_state.v3_max_runup_pct is None else str(st.session_state.v3_max_runup_pct) + '%'}, "
            f"pullback {'Off' if st.session_state.v3_max_pullback_pct is None else str(st.session_state.v3_max_pullback_pct) + '%'}, "
            f"retest {'Off' if int(st.session_state.v3_retest_days) == 0 else str(int(st.session_state.v3_retest_days)) + 'd'}"
        )

        st.sidebar.caption("Note: V3 is stricter than V1/V2. A stock can rank high in V1 but show no V3 signal if it lacks a recent power-candle + volume breakout.")
        st.session_state.v3_show_watchlist_all = st.sidebar.toggle(
            "Show watchlist even without signal",
            value=bool(st.session_state.v3_show_watchlist_all),
            help="If enabled, manually added stocks still appear even when they have no V3/V3tv breakout signal yet.",
        )

        if "v3_breakout_day_only" not in st.session_state:
            st.session_state.v3_breakout_day_only = False
        if "v3_filter_note" not in st.session_state:
            st.session_state.v3_filter_note = None
        if "v3_today_only" not in st.session_state:
            st.session_state.v3_today_only = False
        if "v3_age_1d" not in st.session_state:
            st.session_state.v3_age_1d = True
        st.session_state.v3_breakout_day_only = st.sidebar.toggle(
            "Breakout-day entry only",
            value=bool(st.session_state.v3_breakout_day_only),
            help="Shows only ⚡ BREAKOUT signals with run-up within the current V3 Max Run-up setting.",
        )

        st.session_state.v3_today_only = st.sidebar.toggle(
            "Today breakout only",
            value=bool(st.session_state.v3_today_only),
            help="Shows only ⚡ BREAKOUT signals where the breakout candle happened today (MYT).",
        )

        st.session_state.v3_age_1d = st.sidebar.toggle(
            "Breakout within 1 trading day",
            value=bool(st.session_state.v3_age_1d),
            help="Shows ⚡ BREAKOUT signals whose breakout candle is today or yesterday (more practical with free daily data).",
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
                        max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
                    )
                    _apply_watchlist([res['ticker'] for res in top_breakouts])

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
                    sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                    signal_lookback=st.session_state.v3_signal_lookback,
                    max_runup_pct=st.session_state.v3_max_runup_pct,
                    max_pullback_pct=st.session_state.v3_max_pullback_pct,
                    retest_days=st.session_state.v3_retest_days,
                    max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
                )
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            st.rerun()

    if st.sidebar.button("🔄 Refresh Market Discovery", use_container_width=True):
        with st.spinner("Re-scanning KLCI components..."):
            top_breakouts = get_top_breakouts(
                limit=20,
                model=st.session_state.breakout_model,
                universe_mode=st.session_state.universe_mode,
                sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
                signal_lookback=st.session_state.v3_signal_lookback,
                max_runup_pct=st.session_state.v3_max_runup_pct,
                max_pullback_pct=st.session_state.v3_max_pullback_pct,
                retest_days=st.session_state.v3_retest_days,
                max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
            )
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[:20]))
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
    new_stock = st.sidebar.text_input(
        "Enter Name, Code or Futures (e.g., GENTING, 0166, FKLI)",
        key="add_stock_query",
    )
    if st.sidebar.button("Add to Watchlist", use_container_width=True):
        ticker = search_bursa(new_stock)
        if ticker:
            manual = _uniq_tickers(st.session_state.get("manual_watchlist") or [])
            t_u = str(ticker).upper().strip()
            merged = set(_uniq_tickers(st.session_state.get("watchlist") or []))
            already_pinned = t_u in set(manual)
            if not already_pinned:
                manual.append(t_u)
                st.session_state.manual_watchlist = manual
            _apply_watchlist(st.session_state.get("watchlist") or [])
            try:
                st.session_state.add_stock_query = ""
            except Exception:
                pass
            if already_pinned:
                _notify("info", f"{ticker} is already in your manual watchlist.")
            else:
                if t_u in merged:
                    _notify("success", f"Pinned {ticker} to manual watchlist.")
                else:
                    _notify("success", f"Added {ticker} to watchlist.")
        else:
            _notify("error", "Could not find stock. Try using the exact code (e.g., 5347).")
    try:
        st.sidebar.caption(
            f"Manual: {len(_uniq_tickers(st.session_state.get('manual_watchlist') or []))} | "
            f"Total: {len(_uniq_tickers(st.session_state.get('watchlist') or []))}"
        )
    except Exception:
        pass
    if st.sidebar.button("Clear manual watchlist", use_container_width=True):
        st.session_state.manual_watchlist = []
        _apply_watchlist(st.session_state.get("watchlist") or [])
        st.rerun()

    if st.sidebar.button("🗑️ Reset to Top 20", use_container_width=True):
        top_breakouts = get_top_breakouts(
            limit=20,
            model=st.session_state.breakout_model,
            universe_mode=st.session_state.universe_mode,
            sector_allowlist=(st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3", "v3tv"} else None,
            signal_lookback=st.session_state.v3_signal_lookback,
            max_runup_pct=st.session_state.v3_max_runup_pct,
            max_pullback_pct=st.session_state.v3_max_pullback_pct,
            retest_days=st.session_state.v3_retest_days,
            max_tickers=(st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else (st.session_state.get("intraday_max_tickers") if st.session_state.breakout_model == "v3tv" else None)),
        )
        _apply_watchlist([res['ticker'] for res in top_breakouts])
        st.rerun()

# --- MAIN DASHBOARD TABS ---
tab_stocks, tab_futures, tab_news = st.tabs(["📊 Stock Breakouts", "⛓️ Futures Monitoring", "📰 News & Trends"])

with tab_stocks:
    data_rows = []
    fetch_attempted = 0
    fetch_success = 0
    breakout_model = st.session_state.get("breakout_model", "v2")
    benchmark_df = None
    if breakout_model in {"v2", "v3", "v3tv"}:
        try:
            benchmark_df, _ = get_stock_data("^KLSE", period="1y")
        except Exception:
            benchmark_df = None

    quote_map = None
    intraday_attempted = 0
    quote_success = 0
    if breakout_model == "v3tv":
        try:
            import bursa_core as _core
            codes = []
            for t in st.session_state.watchlist:
                if "=F" in str(t):
                    continue
                code = str(t).upper().strip().split(".")[0]
                if code:
                    codes.append(code)
            seen = set()
            codes_u = []
            for c in codes:
                cu = str(c).upper().strip()
                if not cu or cu in seen:
                    continue
                seen.add(cu)
                codes_u.append(cu)
            max_i = int(st.session_state.get("intraday_max_tickers") or 50)
            if max_i < 1:
                max_i = 50
            req_codes = codes_u[:max_i]
            intraday_attempted = len(req_codes)
            quote_map = {}
            for code in req_codes:
                p = None
                try:
                    p = _core.tradingview_last_price_for_ticker_myr(f"{code}.KL")
                except Exception:
                    p = None
                if p is None:
                    continue
                try:
                    quote_map[str(code).upper().strip()] = {"ld": float(p), "t": int(time.time() * 1000)}
                except Exception:
                    continue
            quote_success = len(quote_map or {})
            if intraday_attempted > 0:
                st.caption(f"TradingView last price: {quote_success}/{intraday_attempted} tickers returned a live price.")
        except Exception:
            quote_map = {}
            quote_success = 0

    # Use a spinner for the load
    with st.spinner("Fetching latest live prices..."):
        manual_set = set(_uniq_tickers(st.session_state.get("manual_watchlist") or []))
        for t in st.session_state.watchlist:
            # Skip futures in the stock tab if they were added manually
            if "=F" in t: continue
            fetch_attempted += 1
            is_manual = str(t).upper().strip() in manual_set
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
                elif breakout_model == "v3tv":
                    code = str(t).upper().strip().split(".")[0]
                    q = (quote_map or {}).get(code) if quote_map is not None else None
                    if analyze_breakout_v3_quote is None:
                        analysis = None
                    else:
                        analysis = analyze_breakout_v3_quote(
                            t,
                            df,
                            q,
                            resolved_name=name,
                            max_runup_pct=st.session_state.v3_max_runup_pct,
                        )
                elif breakout_model == "v2":
                    analysis = analyze_breakout_v2(t, df, name, benchmark_df=benchmark_df, min_rows=min(120, len(df)))
                else:
                    analysis = analyze_breakout(t, df, name)

                if analysis:
                    data_rows.append(analysis)
                elif breakout_model in {"v3", "v3tv"} and (is_manual or bool(st.session_state.get("v3_show_watchlist_all"))):
                    trend = None
                    if breakout_model == "v3tv":
                        try:
                            trend = analyze_breakout_v3(
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
                        except Exception:
                            trend = None
                    try:
                        from ta.momentum import RSIIndicator
                        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
                        rsi_v = float(rsi_v) if pd.notna(rsi_v) else 50.0
                    except Exception:
                        rsi_v = 50.0
                    try:
                        if isinstance(trend, dict) and trend.get("rsi") is not None:
                            rsi_v = float(trend.get("rsi"))
                    except Exception:
                        pass
                    try:
                        last_close = float(df["Close"].iloc[-1])
                    except Exception:
                        last_close = None
                    breakout_level = None
                    try:
                        closes = pd.to_numeric(df["Close"], errors="coerce").dropna()
                        if len(closes) >= 60:
                            breakout_level = float(closes.iloc[-55:-1].max())
                    except Exception:
                        breakout_level = None
                    live_px = None
                    if breakout_model == "v3tv":
                        try:
                            code = str(t).upper().strip().split(".")[0]
                            q = (quote_map or {}).get(code) if quote_map is not None else None
                            if isinstance(q, dict) and q.get("ld") is not None:
                                live_px = float(q.get("ld"))
                        except Exception:
                            live_px = None
                    px = live_px if (live_px is not None) else last_close
                    is_breakout = False
                    runup_pct = None
                    try:
                        if px is not None and breakout_level is not None and float(px) > float(breakout_level) and float(breakout_level) > 0:
                            is_breakout = True
                            runup_pct = ((float(px) / float(breakout_level)) - 1.0) * 100.0
                    except Exception:
                        is_breakout = False
                        runup_pct = None
                    try:
                        _, resolved_name, sector, insight, catalyst = _core._resolve_insight_v3(str(t), name)
                    except Exception:
                        resolved_name = name or str(t)
                        sector = ""
                        insight = ""
                        catalyst = ""
                    try:
                        if isinstance(trend, dict):
                            if trend.get("name"):
                                resolved_name = str(trend.get("name"))
                            if trend.get("sector") is not None:
                                sector = str(trend.get("sector") or "")
                    except Exception:
                        pass
                    score_v = 0
                    score_max_v = 7
                    try:
                        if isinstance(trend, dict) and trend.get("score") is not None:
                            score_v = int(trend.get("score") or 0)
                            score_max_v = int(trend.get("score_max") or 11)
                    except Exception:
                        score_v = 0
                        score_max_v = 7
                    data_rows.append({
                        "ticker": str(t),
                        "name": str(resolved_name or str(t)),
                        "sector": str(sector or ""),
                        "price": float(px) if px is not None else 0.0,
                        "rsi": float(rsi_v),
                        "score": int(score_v),
                        "score_max": int(score_max_v),
                        "breakout_55": bool(is_breakout),
                        "breakout_candle": False,
                        "breakout_candle_valid": False,
                        "breakout_hold_ok": None,
                        "runup_pct": runup_pct,
                        "max_runup_pct": st.session_state.v3_max_runup_pct,
                        "max_pullback_pct": st.session_state.v3_max_pullback_pct,
                        "retest_days": st.session_state.v3_retest_days,
                        "retest_confirmed": False,
                        "breakout_candle_date": "",
                        "breakout_candle_age": None,
                        "breakout_level": breakout_level,
                        "power_candle": None,
                        "volume_spike": None,
                        "liquidity_ok": True,
                        "analysis": str(insight or "Watchlist item (no V3 signal yet)."),
                        "catalyst": str(catalyst or ""),
                        "trend_score": None if trend is None else int(score_v),
                        "trend_score_max": None if trend is None else int(score_max_v),
                        "watch_only": True,
                        "data_ok": True,
                        "model": "v3tv" if breakout_model == "v3tv" else "v3",
                    })
            elif breakout_model in {"v3", "v3tv"} and (is_manual or bool(st.session_state.get("v3_show_watchlist_all"))):
                try:
                    _, resolved_name, sector, insight, catalyst = _core._resolve_insight_v3(str(t), None)
                except Exception:
                    resolved_name = str(t)
                    sector = ""
                    insight = ""
                    catalyst = ""
                live_px = None
                if breakout_model == "v3tv":
                    try:
                        code = str(t).upper().strip().split(".")[0]
                        q = (quote_map or {}).get(code) if quote_map is not None else None
                        if isinstance(q, dict) and q.get("ld") is not None:
                            live_px = float(q.get("ld"))
                    except Exception:
                        live_px = None
                data_rows.append({
                    "ticker": str(t),
                    "name": str(resolved_name or str(t)),
                    "sector": str(sector or ""),
                    "price": float(live_px) if live_px is not None else 0.0,
                    "rsi": 50.0,
                    "score": 0,
                    "score_max": 7,
                    "breakout_55": False,
                    "breakout_candle": False,
                    "breakout_candle_valid": False,
                    "breakout_hold_ok": None,
                    "runup_pct": None,
                    "max_runup_pct": st.session_state.v3_max_runup_pct,
                    "max_pullback_pct": st.session_state.v3_max_pullback_pct,
                    "retest_days": st.session_state.v3_retest_days,
                    "retest_confirmed": False,
                    "breakout_candle_date": "",
                    "breakout_candle_age": None,
                    "breakout_level": None,
                    "power_candle": None,
                    "volume_spike": None,
                    "liquidity_ok": None,
                    "analysis": "No daily price data for this ticker right now (data source blocked or ticker not found).",
                    "catalyst": str(catalyst or ""),
                    "watch_only": True,
                    "data_ok": False,
                    "model": "v3tv" if breakout_model == "v3tv" else "v3",
                })

    if data_rows:
        if breakout_model in {"v3", "v3tv"} and st.session_state.get("v3_filter_note"):
            st.info(str(st.session_state.get("v3_filter_note")))

        if breakout_model in {"v3", "v3tv"}:
            sig_filter = str(st.session_state.get("v3_signal_filter", "all") or "all").lower().strip()
            original_rows = list(data_rows)
            try:
                wl_set = set(_uniq_tickers(st.session_state.get("watchlist") or []))
            except Exception:
                wl_set = set()
            try:
                manual_set2 = set(_uniq_tickers(st.session_state.get("manual_watchlist") or []))
            except Exception:
                manual_set2 = set()
            keep_watch_all = bool(st.session_state.get("v3_show_watchlist_all"))
            watch_rows = [r for r in data_rows if bool(r.get("watch_only"))]
            signal_rows = [r for r in data_rows if not bool(r.get("watch_only"))]
            filtered = list(signal_rows)
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

            if bool(st.session_state.get("v3_today_only")):
                today = pd.Timestamp.now(tz="Asia/Kuala_Lumpur").date()
                tmp = []
                for r in filtered:
                    if not bool(r.get("breakout_candle_valid")):
                        continue
                    d = r.get("breakout_candle_date")
                    if not d:
                        continue
                    try:
                        dd = pd.to_datetime(d).date()
                    except Exception:
                        continue
                    if dd == today:
                        tmp.append(r)
                filtered = tmp

            if bool(st.session_state.get("v3_age_1d")) and (not bool(st.session_state.get("v3_today_only"))):
                tmp = []
                for r in filtered:
                    if not bool(r.get("breakout_candle_valid")):
                        continue
                    age = r.get("breakout_candle_age")
                    try:
                        age_i = int(age) if age is not None else None
                    except Exception:
                        age_i = None
                    if age_i is not None and age_i <= 1:
                        tmp.append(r)
                filtered = tmp

            try:
                filtered_seen = set()
                for r in filtered:
                    t0 = str(r.get("ticker") or "").upper().strip()
                    if t0:
                        filtered_seen.add(t0)
                kept = []
                kept_seen = set()
                for r in signal_rows:
                    t0 = str(r.get("ticker") or "").upper().strip()
                    if not t0:
                        continue
                    if t0 in filtered_seen:
                        continue
                    if t0 in kept_seen:
                        continue
                    if (t0 in manual_set2) or (keep_watch_all and (t0 in wl_set)):
                        kept.append(r)
                        kept_seen.add(t0)
                if kept:
                    filtered = kept + filtered
            except Exception:
                pass

            try:
                final_rows = []
                seen_t = set()
                for r in (watch_rows + filtered):
                    t0 = str(r.get("ticker") or "").upper().strip()
                    if not t0:
                        continue
                    if t0 in seen_t:
                        continue
                    seen_t.add(t0)
                    final_rows.append(r)
                filtered = final_rows
            except Exception:
                if watch_rows:
                    filtered = watch_rows + filtered

            if not filtered:
                st.warning("No matching rows for the selected V3 filter. Showing the full list instead.")
                data_rows = original_rows
            else:
                data_rows = filtered

        if not data_rows:
            st.warning("No matching signals for the selected Entry Style. Try a different universe or style.")
            st.stop()

        # Top Metrics
        if breakout_model in {"v3", "v3tv"}:
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
        try:
            auth_tok = st.session_state.get("auth_token")
        except Exception:
            auth_tok = None
        for r in data_rows:
            ticker_q = quote(str(r.get("ticker") or ""))
            if auth_tok:
                link = f"?chart={ticker_q}&popup=1&auth={quote(str(auth_tok))}"
            else:
                link = f"?chart={ticker_q}&popup=1"
            linked_name = f'<a href="{link}" target="_blank" rel="noopener noreferrer">{r["name"]}</a>'
            score_max = int(r.get("score_max", 5))
            score_val = int(r.get("score", 0))

            if r.get("watch_only"):
                if breakout_model == "v3tv":
                    status = "🔥 STRONG" if score_val >= 8 else ("⚖️ NEUTRAL" if score_val >= 5 else "❄️ WEAK")
                else:
                    status = "👀 WATCH"
            elif breakout_model in {"v3", "v3tv"}:
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

            if r.get("watch_only") and (not bool(r.get("breakout_55"))):
                signal_text = "👀 WATCH"
            else:
                signal_text = "✅ CONFIRMED" if r.get("retest_confirmed") else ("⚡ BREAKOUT" if r.get("breakout_candle_valid") else ("❌ FAILED" if (r.get("breakout_candle") and (r.get("breakout_hold_ok") is False)) else ("⏰ LATE" if r.get("breakout_candle") else ("📈 Breakout" if r.get("breakout_55") else ""))))

            display_rows.append({
                "Ticker": r['ticker'],
                "Name": linked_name,
                "Sector": r.get("sector", ""),
                "Last Price (RM)": f"{float(r['price']):.2f}",
                "Score": f"{score_val}/{score_max}",
                "RSI": r['rsi'],
                "Signal": signal_text,
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
        if breakout_model == "v3tv":
            st.warning("No intraday breakout signals found for the current watchlist and filters.")
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
        try:
            auth_tok = st.session_state.get("auth_token")
        except Exception:
            auth_tok = None
        for r in futures_data:
            ticker_q = quote(str(r.get("ticker") or ""))
            if auth_tok:
                link = f"?chart={ticker_q}&popup=1&auth={quote(str(auth_tok))}"
            else:
                link = f"?chart={ticker_q}&popup=1"
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

with tab_news:
    st.markdown("### 📰 News & Trends")
    st.caption("News is pulled from public RSS sources. Headlines may be delayed and are for informational purposes only.")
    col_a, col_b = st.columns([1, 2])
    with col_a:
        n_limit = st.number_input("Headlines to show", min_value=10, max_value=100, value=40, step=10)
        cache_s = st.number_input("Cache seconds", min_value=60, max_value=3600, value=600, step=60)
        refresh = st.button("🔄 Refresh News", use_container_width=True)
        st.markdown("---")
        include_defaults = st.checkbox("Include default feeds", value=True)
        lang_label = st.selectbox("News language", ["English (MY)", "Malay (MY)"], index=0)
        if lang_label.startswith("Malay"):
            hl, gl, ceid = "ms-MY", "MY", "MY:ms"
        else:
            hl, gl, ceid = "en-MY", "MY", "MY:en"
        topics = [
            "Bursa Malaysia",
            "KLCI",
            "Malaysia OPR",
            "Ringgit",
            "Malaysia inflation",
            "Data center Malaysia",
            "AI Malaysia",
            "Semiconductor Malaysia",
            "Oil price",
            "Brent crude",
            "Malaysia LNG",
            "CPO price",
            "Palm oil Malaysia",
            "Utilities tariff Malaysia",
            "Renewable energy Malaysia",
            "Construction projects Malaysia",
            "MRT Malaysia",
            "REIT Malaysia",
            "Banking Malaysia",
        ]
        selected_topics = st.multiselect("Topics (Google News)", topics, default=["Bursa Malaysia", "KLCI", "Malaysia OPR"])
        custom_queries = st.text_area("Custom Google News queries (one per line)", value="", height=120)
        custom_rss = st.text_area("Custom RSS URLs (one per line)", value="", height=120)
    with col_b:
        if refresh:
            try:
                if hasattr(_core, "_NEWS_CACHE"):
                    _core._NEWS_CACHE.clear()
            except Exception:
                pass

        items = []
        try:
            feed_map = {}
            if include_defaults:
                for q in ["Bursa Malaysia", "KLCI", "Malaysia OPR"]:
                    u = _core.google_news_rss_url(q, hl=hl, gl=gl, ceid=ceid) if hasattr(_core, "google_news_rss_url") else ""
                    if u:
                        feed_map[f"Google News: {q}"] = u
            for q in (selected_topics or []):
                u = _core.google_news_rss_url(q, hl=hl, gl=gl, ceid=ceid) if hasattr(_core, "google_news_rss_url") else ""
                if u:
                    feed_map[f"Google News: {q}"] = u
            for q in [x.strip() for x in str(custom_queries or "").splitlines() if x.strip()]:
                u = _core.google_news_rss_url(q, hl=hl, gl=gl, ceid=ceid) if hasattr(_core, "google_news_rss_url") else ""
                if u:
                    feed_map[f"Google News: {q}"] = u
            for i, u in enumerate([x.strip() for x in str(custom_rss or "").splitlines() if x.strip()], start=1):
                if u.startswith("http"):
                    feed_map[f"RSS: Custom {i}"] = u
            items = _core.get_latest_market_news(limit=int(n_limit), cache_seconds=int(cache_s), feeds=feed_map or None)
        except Exception:
            items = []

        trends = {}
        try:
            trends = _core.infer_market_trends_from_news(items, top_n=8)
        except Exception:
            trends = {}

        try:
            st.caption(f"Feeds active: {0 if 'feed_map' not in locals() else len(feed_map)}")
        except Exception:
            pass

        themes = list((trends or {}).get("themes") or [])
        sectors = list((trends or {}).get("sectors") or [])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Macro Themes (by headline mentions)")
            if themes:
                st.dataframe(pd.DataFrame(themes), use_container_width=True, hide_index=True)
            else:
                st.info("No themes detected from headlines yet.")
        with c2:
            st.markdown("#### Sectors Mentioned (by headline keywords)")
            if sectors:
                st.dataframe(pd.DataFrame(sectors), use_container_width=True, hide_index=True)
            else:
                st.info("No sector signals detected from headlines yet.")

        st.markdown("#### Latest Headlines")
        if not items:
            st.warning("No headlines loaded. Try Refresh News, or check network access in your environment.")
        else:
            rows = []
            for it in items:
                rows.append(
                    {
                        "Time": str(it.get("published") or ""),
                        "Source": str(it.get("source") or ""),
                        "Title": str(it.get("title") or ""),
                        "Link": str(it.get("link") or ""),
                    }
                )
            df_n = pd.DataFrame(rows)
            try:
                def _mk_link(row):
                    u = str(row.get("Link") or "")
                    t = str(row.get("Title") or "")
                    if u.startswith("http"):
                        return f'<a href="{_html_escape(u)}" target="_blank" rel="noopener noreferrer">{_html_escape(t)}</a>'
                    return _html_escape(t)
                df_n["Title"] = df_n.apply(_mk_link, axis=1)
            except Exception:
                pass
            st.markdown(df_n[["Time", "Source", "Title"]].to_html(escape=False, index=False), unsafe_allow_html=True)

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
