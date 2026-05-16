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
import tempfile
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
search_bursa = _core.search_bursa
get_top_breakouts = _core.get_top_breakouts
get_stock_universe = _core.get_stock_universe
BURSA_UNIVERSE_FILE = _core.BURSA_UNIVERSE_FILE
KLCI_COMPONENTS = _core.KLCI_COMPONENTS
get_futures_breakouts = _core.get_futures_breakouts

# --- PAGE CONFIG ---
st.set_page_config(page_title="Lawrence Breakout Analyzer", layout="wide", page_icon="📈")

# --- CACHING (performance) ---
# Streamlit reruns often; caching makes the app feel much faster after the first load.
@st.cache_data(ttl=600, show_spinner=False)
def _cached_stock_data(ticker: str, period: str = "1y"):
    return get_stock_data(ticker, period=period)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_top_breakouts(*, limit: int, model: str, universe_mode: str, sector_allowlist, signal_lookback: int, max_runup_pct, max_pullback_pct, retest_days: int, max_tickers, scan_params: dict):
    return get_top_breakouts(
        limit=limit,
        model=model,
        universe_mode=universe_mode,
        sector_allowlist=sector_allowlist,
        signal_lookback=signal_lookback,
        max_runup_pct=max_runup_pct,
        max_pullback_pct=max_pullback_pct,
        retest_days=retest_days,
        max_tickers=max_tickers,
        **(scan_params or {}),
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_futures_breakouts():
    return get_futures_breakouts()


# --- LOCAL STATE (persistent watchlist/settings) ---
_STATE_FILE_NAME = "bursa_web_state.json"


def _state_file_path() -> Path:
    candidates = []
    try:
        candidates.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        candidates.append(Path.cwd())
    except Exception:
        pass
    try:
        candidates.append(Path(tempfile.gettempdir()))
    except Exception:
        pass

    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d / _STATE_FILE_NAME
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / _STATE_FILE_NAME


def _load_persisted_state() -> dict:
    p = _state_file_path()
    try:
        if not p.exists():
            return {}
        raw = p.read_text(encoding="utf-8", errors="ignore")
        j = json.loads(raw)
        return j if isinstance(j, dict) else {}
    except Exception:
        return {}


def _persisted_state_payload() -> dict:
    keys = [
        "manual_watchlist",
        "universe_mode",
        "breakout_model",
        "top_results_limit",
        "max_tickers_scan",
        "sector_focus",
        "v3_entry_style",
        "v3_signal_filter",
        "v3_signal_lookback",
        "v3_max_runup_pct",
        "v3_max_pullback_pct",
        "v3_retest_days",
        "v3_breakout_buffer_pct",
        "v3_volume_spike_mult",
        "v3_power_close_pos_min",
        "v3_power_body_pct_min",
        "v3_min_traded_value20",
        "v3_require_rs_positive",
        "v3_require_atr_contraction",
        "v3_require_benchmark_trend",
        "show_indicators",
    ]
    out = {"_v": 1}
    for k in keys:
        try:
            if k in st.session_state:
                out[k] = st.session_state.get(k)
        except Exception:
            continue
    return out


def _apply_persisted_state_once() -> None:
    if st.session_state.get("_persist_loaded"):
        return
    st.session_state._persist_loaded = True

    state = _load_persisted_state()
    if not state:
        return

    # Only fill keys that haven't been set in this session.
    for k, v in state.items():
        if k.startswith("_"):
            continue
        if k not in st.session_state:
            st.session_state[k] = v


def _save_state_if_changed() -> None:
    try:
        payload = _persisted_state_payload()
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        if st.session_state.get("_persist_hash") == h:
            return
        st.session_state._persist_hash = h
        _state_file_path().write_text(blob, encoding="utf-8")
    except Exception:
        return


def _fmt_float(v, ndp: int = 4):
    try:
        if v is None:
            return ""
        x = float(v)
        if x != x:
            return ""
        return f"{x:.{int(ndp)}f}"
    except Exception:
        return ""


def _fmt_pct(v, ndp: int = 2):
    try:
        if v is None:
            return ""
        x = float(v)
        if x != x:
            return ""
        return f"{x * 100:.{int(ndp)}f}%"
    except Exception:
        return ""


def _fmt_x(v, ndp: int = 2):
    try:
        if v is None:
            return ""
        x = float(v)
        if x != x:
            return ""
        return f"{x:.{int(ndp)}f}x"
    except Exception:
        return ""

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

    df_chart, name_chart = _cached_stock_data(symbol, period="5y")

    if df_chart is None or df_chart.empty:
        st.warning(f"5-year data unavailable for {symbol}. Trying 1-year data...")
        df_chart, name_chart = _cached_stock_data(symbol, period="1y")

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

    # Optional lightweight indicators panel (MACD + ATR%)
    show_ind = bool(st.session_state.get("show_indicators", True))
    try:
        if popup_mode:
            show_ind = bool(st.checkbox("Show indicators (MACD / ATR%)", value=show_ind))
            st.session_state.show_indicators = show_ind
    except Exception:
        pass

    if show_ind:
        try:
            close = pd.to_numeric(plot_df.get("Close"), errors="coerce")
            high = pd.to_numeric(plot_df.get("High"), errors="coerce")
            low = pd.to_numeric(plot_df.get("Low"), errors="coerce")

            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sig = macd.ewm(span=9, adjust=False).mean()
            hist = macd - sig

            prev_close = close.shift(1)
            tr = pd.concat(
                [
                    (high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr14 = tr.rolling(window=14).mean()
            atr_pct = atr14 / close

            ind_fig = go.Figure()
            ind_fig.add_trace(go.Bar(x=plot_df.index, y=hist, name="MACD Hist", marker_color="rgba(0,200,255,0.55)"))
            ind_fig.add_trace(go.Scatter(x=plot_df.index, y=macd, name="MACD", line=dict(color="white", width=1)))
            ind_fig.add_trace(go.Scatter(x=plot_df.index, y=sig, name="Signal", line=dict(color="orange", width=1)))
            ind_fig.add_trace(go.Scatter(x=plot_df.index, y=atr_pct, name="ATR% (14)", yaxis="y2", line=dict(color="lime", width=1)))

            ind_fig.update_layout(
                title="Indicators (MACD + ATR%)",
                height=360,
                template="plotly_dark",
                yaxis=dict(title="MACD"),
                yaxis2=dict(title="ATR%", overlaying="y", side="right", tickformat=".2%"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(ind_fig, use_container_width=True)
        except Exception:
            st.caption("Indicators unavailable for this chart (insufficient data).")


chart_symbol = _get_query_param("chart")
popup_mode = _get_query_param("popup")

_require_login(bool(popup_mode))

# Load previously saved watchlist/settings (if any) before setting defaults.
_apply_persisted_state_once()

if "breakout_model" not in st.session_state:
    st.session_state.breakout_model = "v3"
if "universe_mode" not in st.session_state:
    st.session_state.universe_mode = "fbm100"
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
if "top_results_limit" not in st.session_state:
    st.session_state.top_results_limit = 20
if "v3_breakout_buffer_pct" not in st.session_state:
    st.session_state.v3_breakout_buffer_pct = 0.0
if "v3_volume_spike_mult" not in st.session_state:
    st.session_state.v3_volume_spike_mult = 1.8
if "v3_power_close_pos_min" not in st.session_state:
    st.session_state.v3_power_close_pos_min = 0.7
if "v3_power_body_pct_min" not in st.session_state:
    st.session_state.v3_power_body_pct_min = 0.55
if "v3_min_traded_value20" not in st.session_state:
    st.session_state.v3_min_traded_value20 = 1_000_000.0
if "v3_require_rs_positive" not in st.session_state:
    st.session_state.v3_require_rs_positive = False
if "v3_require_atr_contraction" not in st.session_state:
    st.session_state.v3_require_atr_contraction = False
if "v3_require_benchmark_trend" not in st.session_state:
    st.session_state.v3_require_benchmark_trend = False
if "show_indicators" not in st.session_state:
    st.session_state.show_indicators = True

# --- UI ---
if not chart_symbol:
    st.title("📈 Lawrence Breakout Analyzer")
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

def _v3_params_for_model(model_key: str) -> dict:
    try:
        m = str(model_key or "").lower().strip()
    except Exception:
        m = ""
    if m != "v3":
        return {}
    try:
        return {
            "breakout_buffer_pct": float(st.session_state.get("v3_breakout_buffer_pct") or 0.0),
            "volume_spike_mult": float(st.session_state.get("v3_volume_spike_mult") or 1.8),
            "power_close_pos_min": float(st.session_state.get("v3_power_close_pos_min") or 0.7),
            "power_body_pct_min": float(st.session_state.get("v3_power_body_pct_min") or 0.55),
            "min_traded_value20": float(st.session_state.get("v3_min_traded_value20") or 1_000_000.0),
            "require_rs_positive": bool(st.session_state.get("v3_require_rs_positive")),
            "require_atr_contraction": bool(st.session_state.get("v3_require_atr_contraction")),
            "require_benchmark_trend": bool(st.session_state.get("v3_require_benchmark_trend")),
        }
    except Exception:
        return {}

def _scan_params_for_model(model_key: str) -> dict:
    return _v3_params_for_model(model_key)


def _ui_get_top_breakouts(limit: int, no_cache: bool = False):
    scan_params = _scan_params_for_model(st.session_state.breakout_model)
    sector_allow = (st.session_state.sector_focus or None) if st.session_state.breakout_model in {"v3"} else None
    max_tickers = st.session_state.max_tickers_scan if st.session_state.universe_mode == "auto" else None
    if no_cache:
        try:
            _cached_top_breakouts.clear()
        except Exception:
            pass
        return get_top_breakouts(
            limit=int(limit),
            model=st.session_state.breakout_model,
            universe_mode=st.session_state.universe_mode,
            sector_allowlist=sector_allow,
            signal_lookback=st.session_state.v3_signal_lookback,
            max_runup_pct=st.session_state.v3_max_runup_pct,
            max_pullback_pct=st.session_state.v3_max_pullback_pct,
            retest_days=st.session_state.v3_retest_days,
            max_tickers=max_tickers,
            **(scan_params or {}),
        )
    return _cached_top_breakouts(
        limit=int(limit),
        model=st.session_state.breakout_model,
        universe_mode=st.session_state.universe_mode,
        sector_allowlist=sector_allow,
        signal_lookback=st.session_state.v3_signal_lookback,
        max_runup_pct=st.session_state.v3_max_runup_pct,
        max_pullback_pct=st.session_state.v3_max_pullback_pct,
        retest_days=st.session_state.v3_retest_days,
        max_tickers=max_tickers,
        scan_params=(scan_params or {}),
    )


# Initialize session state for watchlist
if 'watchlist' not in st.session_state:
    with st.spinner("Initializing Market Discovery..."):
        try:
            top_n = int(st.session_state.get("top_results_limit") or 20)
        except Exception:
            top_n = 20
        if top_n < 10:
            top_n = 10
        if top_n > 200:
            top_n = 200
        top_breakouts = _ui_get_top_breakouts(limit=top_n)
        if top_breakouts:
            _apply_watchlist([res['ticker'] for res in top_breakouts])
        else:
            fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
            _apply_watchlist(list(fallback_universe[:top_n]))

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

    try:
        top_n_ui = int(st.session_state.get("top_results_limit") or 20)
    except Exception:
        top_n_ui = 20
    top_n_ui = st.sidebar.slider("Top N (watchlist size)", min_value=10, max_value=100, value=int(top_n_ui), step=10)
    st.sidebar.caption("If you opened a chart popup window, the sidebar is hidden there. Use the main app tab to change Top N.")
    if int(top_n_ui) != int(st.session_state.get("top_results_limit") or 20):
        st.session_state.top_results_limit = int(top_n_ui)
        with st.spinner("Refreshing list for selected top results..."):
            top_breakouts = _ui_get_top_breakouts(limit=int(st.session_state.top_results_limit))
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[: int(st.session_state.top_results_limit)]))
        st.rerun()

    try:
        top_n = int(st.session_state.get("top_results_limit") or 20)
    except Exception:
        top_n = 20
    if top_n < 10:
        top_n = 10
    if top_n > 200:
        top_n = 200

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
            top_breakouts = _ui_get_top_breakouts(limit=top_n)
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                _apply_watchlist(list(universe_list[:top_n]))
        st.rerun()

    # Index constituent lists (KLCI/FBM70/FBM100/etc.) auto-refresh in the background.
    # Manual update/force-refresh controls are intentionally hidden to keep the UI simple.

    if st.session_state.universe_mode == "auto":
        st.sidebar.caption("Auto universe downloads & caches a Malaysia stock list; the first run may take longer.")
        max_scan = st.sidebar.slider("Max tickers to scan", min_value=50, max_value=1200, value=int(st.session_state.max_tickers_scan), step=50)
        if int(max_scan) != int(st.session_state.max_tickers_scan):
            st.session_state.max_tickers_scan = int(max_scan)
            with st.spinner("Refreshing list for scan size..."):
                top_breakouts = _ui_get_top_breakouts(limit=top_n)
                if top_breakouts:
                    _apply_watchlist([res['ticker'] for res in top_breakouts])
                else:
                    fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                    _apply_watchlist(list(fallback_universe[:top_n]))
            st.rerun()
    if st.session_state.universe_mode == "file":
        st.sidebar.caption("Universe source: bursa_universe.csv in the app folder. Put one 4-digit stock code per line (Main + ACE). Example: 6742 or 6742.KL.")

    st.sidebar.toggle(
        "Show indicator columns (MACD/ATR/Vol)",
        value=bool(st.session_state.get("show_indicators", True)),
        key="show_indicators",
        help="Adds extra columns to the tables and shows an extra indicator panel in the chart view.",
    )

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
            top_breakouts = _ui_get_top_breakouts(limit=top_n)
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[:top_n]))
        st.rerun()


    if st.session_state.breakout_model == "v3":
        if "v3_entry_style" not in st.session_state:
            st.session_state.v3_entry_style = "Early Entry"
        if "v3_signal_filter" not in st.session_state:
            st.session_state.v3_signal_filter = "all"
        if "v3_show_watchlist_all" not in st.session_state:
            st.session_state.v3_show_watchlist_all = True
        if "v3_signals_only" not in st.session_state:
            st.session_state.v3_signals_only = False

        entry_options = [
            "Early Entry (Recommended)",
            "Balanced",
            "Confirmed",
            "Late (Chasing Risk)",
            "Failed (Breakout Broke)",
            "Custom (Manual)",
        ]
        entry_idx = 0
        if str(st.session_state.v3_entry_style).startswith("Early"):
            entry_idx = 0
        elif str(st.session_state.v3_entry_style).startswith("Balanced"):
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
                st.session_state.v3_breakout_buffer_pct = 0.0
                st.session_state.v3_volume_spike_mult = 1.8
                st.session_state.v3_power_close_pos_min = 0.7
                st.session_state.v3_power_body_pct_min = 0.55
                st.session_state.v3_min_traded_value20 = 1_000_000.0
                st.session_state.v3_require_rs_positive = False
                st.session_state.v3_require_atr_contraction = False
                st.session_state.v3_require_benchmark_trend = False
            elif selected_style == "Balanced":
                st.session_state.v3_signal_filter = "all"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = 8.0
                st.session_state.v3_max_pullback_pct = 3.0
                st.session_state.v3_retest_days = 3
                st.session_state.v3_breakout_buffer_pct = 0.0
                st.session_state.v3_volume_spike_mult = 1.8
                st.session_state.v3_power_close_pos_min = 0.7
                st.session_state.v3_power_body_pct_min = 0.55
                st.session_state.v3_min_traded_value20 = 1_000_000.0
                st.session_state.v3_require_rs_positive = False
                st.session_state.v3_require_atr_contraction = False
                st.session_state.v3_require_benchmark_trend = False
            elif selected_style == "Confirmed":
                st.session_state.v3_signal_filter = "all"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = None
                st.session_state.v3_max_pullback_pct = 3.0
                st.session_state.v3_retest_days = 5
                st.session_state.v3_breakout_buffer_pct = 0.0
                st.session_state.v3_volume_spike_mult = 1.8
                st.session_state.v3_power_close_pos_min = 0.7
                st.session_state.v3_power_body_pct_min = 0.55
                st.session_state.v3_min_traded_value20 = 1_000_000.0
                st.session_state.v3_require_rs_positive = False
                st.session_state.v3_require_atr_contraction = False
                st.session_state.v3_require_benchmark_trend = False
            elif selected_style == "Late":
                st.session_state.v3_signal_filter = "late"
                st.session_state.v3_signal_lookback = 10
                st.session_state.v3_max_runup_pct = 5.0
                st.session_state.v3_max_pullback_pct = 2.0
                st.session_state.v3_retest_days = 0
                st.session_state.v3_breakout_buffer_pct = 0.0
                st.session_state.v3_volume_spike_mult = 1.8
                st.session_state.v3_power_close_pos_min = 0.7
                st.session_state.v3_power_body_pct_min = 0.55
                st.session_state.v3_min_traded_value20 = 1_000_000.0
                st.session_state.v3_require_rs_positive = False
                st.session_state.v3_require_atr_contraction = False
                st.session_state.v3_require_benchmark_trend = False
            else:
                if selected_style == "Failed":
                    st.session_state.v3_signal_filter = "failed"
                    st.session_state.v3_signal_lookback = 10
                    st.session_state.v3_max_runup_pct = None
                    st.session_state.v3_max_pullback_pct = 2.0
                    st.session_state.v3_retest_days = 0
                    st.session_state.v3_breakout_buffer_pct = 0.0
                    st.session_state.v3_volume_spike_mult = 1.8
                    st.session_state.v3_power_close_pos_min = 0.7
                    st.session_state.v3_power_body_pct_min = 0.55
                    st.session_state.v3_min_traded_value20 = 1_000_000.0
                    st.session_state.v3_require_rs_positive = False
                    st.session_state.v3_require_atr_contraction = False
                    st.session_state.v3_require_benchmark_trend = False

            with st.spinner("Applying entry style..."):
                if st.session_state.v3_signal_filter in {"late", "failed"}:
                    scan_limit = 9999
                else:
                    try:
                        scan_limit = int(st.session_state.get("top_results_limit") or 20)
                    except Exception:
                        scan_limit = 20
                    if scan_limit < 10:
                        scan_limit = 10
                    if scan_limit > 200:
                        scan_limit = 200
                top_breakouts = _ui_get_top_breakouts(limit=scan_limit)
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
            f"retest {'Off' if int(st.session_state.v3_retest_days) == 0 else str(int(st.session_state.v3_retest_days)) + 'd'}, "
            f"buffer {float(st.session_state.v3_breakout_buffer_pct):.1f}%, "
            f"vol {float(st.session_state.v3_volume_spike_mult):.1f}x, "
            f"liq RM{int(float(st.session_state.v3_min_traded_value20)):,}"
        )

        st.sidebar.caption("Note: V3 is stricter than V1/V2. A stock can rank high in V1 but show no V3 signal if it lacks a recent power-candle + volume breakout.")
        if st.session_state.breakout_model == "v3":
            st.session_state.v3_signals_only = st.sidebar.toggle(
                "Show only valid V3 signals",
                value=bool(st.session_state.v3_signals_only),
                help="If enabled, shows only V3 signals where ⚡ BREAKOUT (or retest-confirmed) is true. This will hide 🟡 NEAR hints.",
            )
            st.session_state.v3_show_watchlist_all = False
        else:
            st.session_state.v3_show_watchlist_all = st.sidebar.toggle(
                "Show watchlist even without signal",
                value=bool(st.session_state.v3_show_watchlist_all),
                help="If enabled, manually added stocks still appear even when they have no breakout signal yet.",
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
            help="Shows only ⚡ BREAKOUT signals with run-up within the current V3 Max Run-up setting. This will hide 🟡 NEAR hints.",
        )

        st.session_state.v3_today_only = st.sidebar.toggle(
            "Today breakout only",
            value=bool(st.session_state.v3_today_only),
            help="Shows only ⚡ BREAKOUT signals where the breakout candle happened today (MYT). This will hide 🟡 NEAR hints.",
        )

        st.session_state.v3_age_1d = st.sidebar.toggle(
            "Breakout within 1 trading day",
            value=bool(st.session_state.v3_age_1d),
            help="Shows ⚡ BREAKOUT signals whose breakout candle is today or yesterday (more practical with free daily data). This will hide 🟡 NEAR hints.",
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
                    top_breakouts = _ui_get_top_breakouts(limit=top_n)
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
                top_breakouts = _ui_get_top_breakouts(limit=top_n)
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            st.rerun()

    if st.sidebar.button("🔄 Refresh Market Discovery", use_container_width=True):
        with st.spinner("Refreshing Market Discovery..."):
            top_breakouts = _ui_get_top_breakouts(limit=top_n)
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[:top_n]))
            _notify("success", "Dashboard updated!")
            st.rerun()

    if st.sidebar.button("⚡ Fetch Latest Now (no cache)", use_container_width=True):
        with st.spinner("Fetching latest candles (no cache)..."):
            try:
                _cached_stock_data.clear()
            except Exception:
                pass
            top_breakouts = _ui_get_top_breakouts(limit=top_n, no_cache=True)
            if top_breakouts:
                _apply_watchlist([res['ticker'] for res in top_breakouts])
            else:
                fallback_universe, _ = get_stock_universe(st.session_state.universe_mode)
                _apply_watchlist(list(fallback_universe[:top_n]))
            _notify("success", "Fetched latest candles (no cache).")
            st.rerun()

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

    # --- Downloads (Watchlist) ---
    st.sidebar.markdown("---")
    st.sidebar.header("⬇️ Downloads")
    try:
        wl = _uniq_tickers(st.session_state.get("watchlist") or [])
        manual_wl = set(_uniq_tickers(st.session_state.get("manual_watchlist") or []))
        rows = []
        for t in wl:
            kind = "Futures" if "=F" in t else ("Index" if str(t).startswith("^") else "Stock")
            rows.append({"ticker": t, "type": kind, "pinned": bool(t in manual_wl)})
        wl_df = pd.DataFrame(rows)
        wl_csv = wl_df.to_csv(index=False).encode("utf-8")
        wl_txt = ("\n".join(wl) + ("\n" if wl else "")).encode("utf-8")
        st.sidebar.download_button("Download watchlist (CSV)", data=wl_csv, file_name="watchlist.csv", mime="text/csv", use_container_width=True)
        st.sidebar.download_button("Download watchlist (TXT)", data=wl_txt, file_name="watchlist.txt", mime="text/plain", use_container_width=True)
    except Exception:
        pass

    if st.sidebar.button(f"🗑️ Reset to Top {top_n}", use_container_width=True):
        top_breakouts = _ui_get_top_breakouts(limit=top_n)
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
    if breakout_model in {"v2", "v3"}:
        try:
            benchmark_df, _ = _cached_stock_data("^KLSE", period="1y")
        except Exception:
            benchmark_df = None

    # Use a spinner for the load
    with st.spinner("Fetching latest live prices..."):
        manual_set = set(_uniq_tickers(st.session_state.get("manual_watchlist") or []))
        for t in st.session_state.watchlist:
            # Skip futures in the stock tab if they were added manually
            if "=F" in t: continue
            fetch_attempted += 1
            is_manual = str(t).upper().strip() in manual_set
            df, name = _cached_stock_data(t, period="1y")
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
                        **_v3_params_for_model("v3"),
                    )
                elif breakout_model == "v2":
                    analysis = analyze_breakout_v2(t, df, name, benchmark_df=benchmark_df, min_rows=min(120, len(df)))
                else:
                    analysis = analyze_breakout(t, df, name)

                if analysis:
                    data_rows.append(analysis)
                elif breakout_model != "v3" and (is_manual or bool(st.session_state.get("v3_show_watchlist_all"))):
                    try:
                        from ta.momentum import RSIIndicator
                        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
                        rsi_v = float(rsi_v) if pd.notna(rsi_v) else 50.0
                    except Exception:
                        rsi_v = 50.0
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
                    px = last_close
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
                    data_rows.append({
                        "ticker": str(t),
                        "name": str(resolved_name or str(t)),
                        "sector": str(sector or ""),
                        "price": float(px) if px is not None else 0.0,
                        "rsi": float(rsi_v),
                        "score": 0,
                        "score_max": 7,
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
                        "analysis": str(insight or "Watchlist item (no signal yet)."),
                        "catalyst": str(catalyst or ""),
                        "watch_only": True,
                        "data_ok": True,
                        "model": str(breakout_model),
                    })
            elif breakout_model != "v3" and (is_manual or bool(st.session_state.get("v3_show_watchlist_all"))):
                try:
                    _, resolved_name, sector, insight, catalyst = _core._resolve_insight_v3(str(t), None)
                except Exception:
                    resolved_name = str(t)
                    sector = ""
                    insight = ""
                    catalyst = ""
                data_rows.append({
                    "ticker": str(t),
                    "name": str(resolved_name or str(t)),
                    "sector": str(sector or ""),
                    "price": 0.0,
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
                    "model": str(breakout_model),
                })

    if data_rows:
        if breakout_model == "v3" and st.session_state.get("v3_filter_note"):
            st.info(str(st.session_state.get("v3_filter_note")))

        if breakout_model == "v3":
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
            if breakout_model == "v3":
                wl_set = set()
                manual_set2 = set()
                keep_watch_all = False
                watch_rows = []
                if bool(st.session_state.get("v3_signals_only")):
                    try:
                        filtered = [r for r in filtered if bool(r.get("breakout_candle_valid")) or bool(r.get("retest_confirmed"))]
                    except Exception:
                        filtered = []
                    original_rows = list(filtered)
            if breakout_model == "v3" and sig_filter in {"late", "failed"}:
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

            if breakout_model == "v3" and bool(st.session_state.get("v3_breakout_day_only")):
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

            if breakout_model == "v3" and bool(st.session_state.get("v3_today_only")):
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

            if breakout_model == "v3" and bool(st.session_state.get("v3_age_1d")) and (not bool(st.session_state.get("v3_today_only"))):
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

            if not filtered:
                st.warning("No V3 signals match the current filters.")
                data_rows = []
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
        export_rows = []
        show_ind = bool(st.session_state.get("show_indicators", True))
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
                status = " WATCH"
            elif breakout_model == "v3":
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
            elif (not bool(r.get("breakout_candle_valid"))) and (not bool(r.get("retest_confirmed"))) and bool(r.get("near_breakout")):
                signal_text = "🟡 NEAR"
            else:
                signal_text = "✅ CONFIRMED" if r.get("retest_confirmed") else ("⚡ BREAKOUT" if r.get("breakout_candle_valid") else ("❌ FAILED" if (r.get("breakout_candle") and (r.get("breakout_hold_ok") is False)) else ("⏰ LATE" if r.get("breakout_candle") else ("📈 Breakout" if r.get("breakout_55") else ""))))

            runup_or_dist = r.get("runup_pct")
            if runup_or_dist is None and r.get("distance_to_breakout_pct") is not None:
                runup_or_dist = r.get("distance_to_breakout_pct")

            disp = {
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
                "Run-up %": "" if runup_or_dist is None else f"{float(runup_or_dist):.1f}%",
                "Status": status,
                "Catalyst / Insight": (r['catalyst'] if score_val >= neutral_threshold else r['analysis'])
            }
            exp = {
                "Ticker": str(r.get("ticker") or ""),
                "Name": str(r.get("name") or ""),
                "Sector": str(r.get("sector") or ""),
                "Last Price (RM)": float(r.get("price") or 0.0),
                "Score": f"{score_val}/{score_max}",
                "RSI": float(r.get("rsi") or 0.0),
                "Signal": str(signal_text),
                "Signal Date": str(r.get("breakout_candle_date") or ""),
                "Retest Confirmed": bool(r.get("retest_confirmed")),
                "Retest Date": str(r.get("retest_touch_date") or ""),
                "Run-up %": None if runup_or_dist is None else float(runup_or_dist),
                "Status": str(status).strip(),
                "Catalyst": str(r.get("catalyst") or ""),
                "Insight": str(r.get("analysis") or ""),
            }

            if show_ind:
                disp["MACD Hist"] = _fmt_float(r.get("macd_hist"), 4)
                disp["ATR% (14)"] = _fmt_pct(r.get("atr_pct"), 2)
                disp["Vol/Avg20"] = _fmt_x(r.get("vol_ratio20"), 2)
                exp["MACD Hist"] = None if r.get("macd_hist") is None else float(r.get("macd_hist"))
                exp["ATR% (14)"] = None if r.get("atr_pct") is None else float(r.get("atr_pct"))
                exp["Vol/Avg20"] = None if r.get("vol_ratio20") is None else float(r.get("vol_ratio20"))

            display_rows.append(disp)
            export_rows.append(exp)
        
        df_display = pd.DataFrame(display_rows)
        df_export = pd.DataFrame(export_rows)
        st.caption("Tip: click the stock name to open its chart in a new window/tab.")
        try:
            st.download_button(
                "Download Stock Breakouts (CSV)",
                data=df_export.to_csv(index=False).encode("utf-8"),
                file_name="stock_breakouts.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except Exception:
            pass
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.warning("No data found. Please click 'Refresh Market Discovery' or add valid tickers.")
        st.caption(f"Fetch summary: {fetch_success}/{fetch_attempted} tickers returned data.")
        if fetch_attempted == 0:
            st.caption("Watchlist is empty. Try switching universe, clicking 'Refresh Market Discovery', or resetting to the top list.")
        st.caption("If this stays 0, Yahoo data may be blocked/rate-limited in your environment. Try again later, reduce scan size, or switch to a smaller universe (KLCI/Top100).")
        st.caption("Optional fallback: set BURSA_PRICE_API_BASE_URL and BURSA_PRICE_API_KEY in your environment to use a non-Yahoo data source.")

with tab_futures:
    st.markdown("### ⛓️ Malaysian Futures Dashboard")
    st.info("Monitoring FKLI, FCPO, and FM70 for technical breakouts.")
    
    futures_data = []
    with st.spinner("Analyzing Futures market..."):
        futures_data = _cached_futures_breakouts()
    
    if futures_data:
        futures_display = []
        futures_export = []
        show_ind = bool(st.session_state.get("show_indicators", True))
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
            score_max = int(r.get("score_max", 5))
            score_val = int(r.get("score", 0))
            disp = {
                "Future Contract": linked_name,
                "Ticker": r['ticker'],
                "Last Price (RM)": f"{float(r['price']):.2f}",
                "Breakout Score": f"{score_val}/{score_max}",
                "RSI": r['rsi'],
                "Momentum": "🚀 BULLISH" if score_val >= 4 else ("⚖️ SIDEWAYS" if score_val >= 2 else "📉 BEARISH"),
                "Technical View": r['analysis']
            }
            exp = {
                "Ticker": str(r.get("ticker") or ""),
                "Name": str(r.get("name") or ""),
                "Last Price (RM)": float(r.get("price") or 0.0),
                "Score": f"{score_val}/{score_max}",
                "RSI": float(r.get("rsi") or 0.0),
                "Technical View": str(r.get("analysis") or ""),
            }
            if show_ind:
                disp["MACD Hist"] = _fmt_float(r.get("macd_hist"), 4)
                disp["ATR% (14)"] = _fmt_pct(r.get("atr_pct"), 2)
                disp["Vol/Avg20"] = _fmt_x(r.get("vol_ratio20"), 2)
                exp["MACD Hist"] = None if r.get("macd_hist") is None else float(r.get("macd_hist"))
                exp["ATR% (14)"] = None if r.get("atr_pct") is None else float(r.get("atr_pct"))
                exp["Vol/Avg20"] = None if r.get("vol_ratio20") is None else float(r.get("vol_ratio20"))

            futures_display.append(disp)
            futures_export.append(exp)
        
        df_futures = pd.DataFrame(futures_display)
        df_futures_export = pd.DataFrame(futures_export)
        st.caption("Tip: click the futures contract name to open its chart in a new window/tab.")
        try:
            st.download_button(
                "Download Futures Table (CSV)",
                data=df_futures_export.to_csv(index=False).encode("utf-8"),
                file_name="futures_breakouts.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except Exception:
            pass
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
        include_my_defaults = st.checkbox("Include Malaysia default feeds", value=True)
        include_global_defaults = st.checkbox("Include global macro default feeds", value=True)
        lang_label = st.selectbox("Malaysia news language", ["English (MY)", "Malay (MY)"], index=0)
        if lang_label.startswith("Malay"):
            hl, gl, ceid = "ms-MY", "MY", "MY:ms"
        else:
            hl, gl, ceid = "en-MY", "MY", "MY:en"
        global_region = st.selectbox("Global region", ["US/Global (English)", "UK/Global (English)"], index=0)
        if global_region.startswith("UK"):
            ghl, ggl, gceid = "en-GB", "GB", "GB:en"
        else:
            ghl, ggl, gceid = "en-US", "US", "US:en"

        topics = [
            "Bursa Malaysia",
            "KLCI",
            "Malaysia OPR",
            "Ringgit",
            "Malaysia inflation",
            "Malaysia GDP",
            "Malaysia budget",
            "Bank Negara Malaysia",
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
        selected_topics = st.multiselect(
            "Malaysia topics (Google News)",
            topics,
            default=[
                "Bursa Malaysia",
                "KLCI",
                "Malaysia OPR",
                "Ringgit",
                "Malaysia inflation",
                "Bank Negara Malaysia",
                "Data center Malaysia",
                "CPO price",
                "Utilities tariff Malaysia",
                "REIT Malaysia",
                "Banking Malaysia",
            ],
        )

        global_topics = [
            "US Federal Reserve",
            "FOMC",
            "US CPI",
            "US jobs report",
            "US Treasury yields",
            "S&P 500",
            "Nasdaq",
            "VIX",
            "US Iran tensions",
            "Iran Israel conflict",
            "Strait of Hormuz",
            "Middle East conflict",
            "Oil price",
            "OPEC",
            "Brent crude",
            "Gold price",
            "China stimulus",
            "China property",
            "US China trade",
            "Ukraine war",
            "Global recession",
        ]
        selected_global_topics = st.multiselect(
            "Global macro topics (Google News)",
            global_topics,
            default=[
                "US Federal Reserve",
                "FOMC",
                "US CPI",
                "US jobs report",
                "US Treasury yields",
                "S&P 500",
                "Nasdaq",
                "US Iran tensions",
                "Middle East conflict",
                "Strait of Hormuz",
                "Oil price",
                "OPEC",
                "Gold price",
                "China stimulus",
                "Ukraine war",
                "VIX",
            ],
        )

        custom_queries = st.text_area("Custom Malaysia Google News queries (one per line)", value="", height=90)
        custom_global_queries = st.text_area("Custom global Google News queries (one per line)", value="", height=90)
        custom_rss = st.text_area("Custom RSS URLs (one per line)", value="", height=90)
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
            if include_my_defaults:
                for q in ["Bursa Malaysia", "KLCI", "Malaysia OPR", "Ringgit", "Malaysia inflation", "Bank Negara Malaysia", "Malaysia GDP"]:
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
            if include_global_defaults:
                for q in ["US Iran tensions", "Middle East conflict", "Strait of Hormuz", "US Federal Reserve", "FOMC", "US CPI", "US jobs report", "US Treasury yields", "S&P 500", "Nasdaq", "VIX", "Oil price", "OPEC", "Gold price", "China stimulus", "Ukraine war"]:
                    u = _core.google_news_rss_url(q, hl=ghl, gl=ggl, ceid=gceid) if hasattr(_core, "google_news_rss_url") else ""
                    if u:
                        feed_map[f"Global: {q}"] = u
            for q in (selected_global_topics or []):
                u = _core.google_news_rss_url(q, hl=ghl, gl=ggl, ceid=gceid) if hasattr(_core, "google_news_rss_url") else ""
                if u:
                    feed_map[f"Global: {q}"] = u
            for q in [x.strip() for x in str(custom_global_queries or "").splitlines() if x.strip()]:
                u = _core.google_news_rss_url(q, hl=ghl, gl=ggl, ceid=gceid) if hasattr(_core, "google_news_rss_url") else ""
                if u:
                    feed_map[f"Global: {q}"] = u
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

        notes = []
        try:
            notes = _core.summarize_market_impacts(trends) if hasattr(_core, "summarize_market_impacts") else []
        except Exception:
            notes = []
        if notes:
            st.markdown("#### What may move markets (headline-based)")
            for n in notes:
                st.write(f"- {str(n)}")

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
