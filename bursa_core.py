import os
import pandas as pd
import datetime
import requests
import re
import csv
import time

cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if os.environ.get("STREAMLIT_SERVER_PORT") or not os.access(os.getcwd(), os.W_OK):
    cache_path = "/tmp/.yfinance_cache"
try:
    os.makedirs(cache_path, exist_ok=True)
except Exception:
    pass
os.environ["YFINANCE_CACHE_DIR"] = cache_path

import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

try:
    yf.set_tz_cache_location(cache_path)
except Exception:
    pass

# --- KNOWLEDGE BASE: LATEST MARKET INSIGHTS (MAY 2026) ---
MARKET_INSIGHTS = {
    "1155.KL": {"code": "1155", "name": "MAYBANK", "sector": "Banking", "analysis": "Strong defensive play with attractive dividends.", "catalyst": "High interest rate environment."},
    "1295.KL": {"code": "1295", "name": "PBBANK", "sector": "Banking", "analysis": "Strong asset quality and consistent dividends.", "catalyst": "Economic recovery proxy."},
    "1023.KL": {"code": "1023", "name": "CIMB", "sector": "Banking", "analysis": "Leading ASEAN focused bank. Strong earnings growth.", "catalyst": "Regional growth momentum."},
    "5347.KL": {"code": "5347", "name": "TNB", "sector": "Utilities", "analysis": "Top pick for FY26. Grid investments and renewable energy.", "catalyst": "National Energy Transition Roadmap (NETR)."},
    "5183.KL": {"code": "5183", "name": "PCHEM", "sector": "Chemicals", "analysis": "Proxy for global economic recovery and oil prices.", "catalyst": "Product price stabilization."},
    "5225.KL": {"code": "5225", "name": "IHH", "sector": "Healthcare", "analysis": "Global healthcare leader with strong expansion plans.", "catalyst": "Medical tourism and aging population."},
    "6947.KL": {"code": "6947", "name": "DIGI", "sector": "Telecommunications", "analysis": "Post-merger synergies and 5G leadership.", "catalyst": "Digital economy growth."},
    "6888.KL": {"code": "6888", "name": "AXIATA", "sector": "Telecommunications", "analysis": "Regional footprint and digital assets expansion.", "catalyst": "TowerCo monetization."},
    "6012.KL": {"code": "6012", "name": "MAXIS", "sector": "Telecommunications", "analysis": "Strong mobile market share and 5G rollout.", "catalyst": "Enterprise digital transformation."},
    "5819.KL": {"code": "5819", "name": "HLBANK", "sector": "Banking", "analysis": "Excellent asset quality and cost management.", "catalyst": "Mortgage and SME loan growth."},
    "8869.KL": {"code": "8869", "name": "PGENE", "sector": "Utilities", "analysis": "Stable earnings from power generation.", "catalyst": "New PPA agreements."},
    "6033.KL": {"code": "6033", "name": "PETGAS", "sector": "Utilities", "analysis": "Defensive play with high yields.", "catalyst": "Regulated asset base growth."},
    "3816.KL": {"code": "3816", "name": "MISC", "sector": "Transportation", "analysis": "Long-term charter contracts provide stability.", "catalyst": "Global energy demand."},
    "1066.KL": {"code": "1066", "name": "RHBBANK", "sector": "Banking", "analysis": "Attractive dividend yields and digital banking.", "catalyst": "Transformation program success."},
    "4707.KL": {"code": "4707", "name": "NESTLE", "sector": "Consumer", "analysis": "Resilient demand for essential products.", "catalyst": "Input cost normalization."},
    "1961.KL": {"code": "1961", "name": "IOICORP", "sector": "Plantation", "analysis": "Efficient producer with strong integrated operations.", "catalyst": "CPO price support."},
    "2445.KL": {"code": "2445", "name": "KLK", "sector": "Plantation", "analysis": "Leading plantation group with strong downstream.", "catalyst": "Upstream production growth."},
    "4065.KL": {"code": "4065", "name": "PPB", "sector": "Consumer", "analysis": "Strong contribution from Wilmar and flour business.", "catalyst": "Food security themes."},
    "3182.KL": {"code": "3182", "name": "GENTING", "sector": "Tourism", "analysis": "Proxy for global travel recovery.", "catalyst": "Resorts World Las Vegas performance."},
    "4715.KL": {"code": "4715", "name": "GENM", "sector": "Tourism", "analysis": "Direct beneficiary of Visit Malaysia Year 2026.", "catalyst": "Increased tourist arrivals."},
    "7277.KL": {"code": "7277", "name": "DIALOG", "sector": "Oil & Gas", "analysis": "Strong recurring income from storage assets.", "catalyst": "Pengerang Phase 3 development."},
    "4197.KL": {"code": "4197", "name": "SIME", "sector": "Conglomerate", "analysis": "Strong automotive and heavy equipment division.", "catalyst": "EV market expansion."},
    "5285.KL": {"code": "5285", "name": "SIMEPLT", "sector": "Plantation", "analysis": "World's largest producer of certified sustainable CPO.", "catalyst": "ESG leadership and yield recovery."},
    "5681.KL": {"code": "5681", "name": "PETDAG", "sector": "Retail", "analysis": "Dominant market share in retail fuel.", "catalyst": "Domestic travel volume."},
    "1015.KL": {"code": "1015", "name": "AMBANK", "sector": "Banking", "analysis": "Corporate banking strength and cost discipline.", "catalyst": "Asset quality improvement."},
    "1082.KL": {"code": "1082", "name": "HLFG", "sector": "Banking", "analysis": "Undervalued financial holding company.", "catalyst": "Subsidiaries' strong performance."},
    "0166.KL": {"code": "0166", "name": "INARI", "sector": "Technology", "analysis": "Proxy for global 5G and AI smartphone cycle.", "catalyst": "New product launches by key customers."},
    "5296.KL": {"code": "5296", "name": "MRDIY", "sector": "Consumer", "analysis": "Aggressive store expansion and resilient demand.", "catalyst": "Inflationary environment beneficiary."},
    "5246.KL": {"code": "5246", "name": "WESTPORTS", "sector": "Transportation", "analysis": "Proxy for global trade recovery.", "catalyst": "Port expansion plans."},
    "4677.KL": {"code": "4677", "name": "YTL", "sector": "Conglomerate", "analysis": "Strong performance from utility and data center divisions.", "catalyst": "AI data center development."},
    "6742.KL": {"code": "6742", "name": "YTLPOWR", "sector": "Utilities", "analysis": "Power & utilities leader with data center-related growth exposure.", "catalyst": "Electricity demand growth and digital infrastructure theme."},
    "7148.KL": {"code": "7148", "name": "DPHARMA", "sector": "Healthcare", "analysis": "Strong local pharmaceutical market share.", "catalyst": "Public healthcare spending."},
    "5099.KL": {"code": "5099", "name": "CAPITALA", "sector": "Aviation", "analysis": "Proxy for regional travel surge.", "catalyst": "AirAsia recovery and digital assets."},
    "FKLI=F": {"code": "FKLI", "name": "KLCI FUTURES", "sector": "Futures", "analysis": "Proxy for the underlying FBM KLCI index. High correlation with banking and utility heavyweights.", "catalyst": "Market sentiment and index component performance."},
    "FCPO=F": {"code": "FCPO", "name": "CPO FUTURES", "sector": "Futures", "analysis": "Global benchmark for Crude Palm Oil. Driven by edible oil supply/demand and biodiesel mandates.", "catalyst": "Indonesian export policies and weather patterns."},
    "FM70=F": {"code": "FM70", "name": "MID 70 FUTURES", "sector": "Futures", "analysis": "Proxy for the FBM Mid 70 Index, representing mid-cap growth stocks.", "catalyst": "Domestic liquidity and mid-cap earnings momentum."}
}

def _tradingview_last_price_myr(symbol_path: str):
    try:
        url = f"https://www.tradingview.com/symbols/{symbol_path}/"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).text
        m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*MYR", html)
        if not m:
            return None
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


TRADINGVIEW_PRICE_OVERLAY_ENABLED = False
TRADINGVIEW_PRICE_CACHE_SECONDS = 60
_TV_PRICE_CACHE: dict[str, tuple[float, float]] = {}

ITICK_BASE_URL = os.environ.get("ITICK_BASE_URL") or "https://api.itick.org"
ITICK_DEFAULT_REGION = os.environ.get("ITICK_REGION") or "MY"
ITICK_CACHE_SECONDS = 20
_ITICK_KLINE_CACHE: dict[str, tuple[float, dict]] = {}
_ITICK_INFO_CACHE: dict[str, tuple[float, str]] = {}
ITICK_INFO_CACHE_SECONDS = 24 * 3600


def _get_itick_token() -> str | None:
    try:
        token = os.environ.get("ITICK_TOKEN") or os.environ.get("itick_token")
        if token:
            token_s = str(token).strip()
            if token_s:
                return token_s
    except Exception:
        pass

    try:
        import streamlit as st  # type: ignore
        try:
            ss = getattr(st, "session_state", None)
            if ss is not None:
                for k in ["ITICK_TOKEN", "itick_token", "itick_token_input"]:
                    try:
                        v = ss.get(k)
                    except Exception:
                        try:
                            v = ss[k]
                        except Exception:
                            v = None
                    if v:
                        v_s = str(v).strip()
                        if v_s:
                            return v_s
        except Exception:
            pass
        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return None
        for k in ["ITICK_TOKEN", "itick_token", "ITICK_API_TOKEN", "itick_api_token"]:
            try:
                if k in secrets:
                    v = secrets[k]
                else:
                    v = None
            except Exception:
                try:
                    v = secrets.get(k)
                except Exception:
                    v = None
            if v:
                v_s = str(v).strip()
                if v_s:
                    return v_s
        return None
    except Exception:
        return None


def itick_enabled() -> bool:
    try:
        return bool(_get_itick_token())
    except Exception:
        return False


def _itick_get_json(path: str, params: dict) -> dict | None:
    try:
        token = _get_itick_token()
        if not token:
            return None
        url = str(ITICK_BASE_URL).rstrip("/") + str(path)
        r = requests.get(
            url,
            params=params,
            headers={"accept": "application/json", "token": token, "User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        j = r.json()
        if not isinstance(j, dict):
            return None
        if int(j.get("code", 0) or 0) != 0:
            return None
        return j
    except Exception:
        return None


def _itick_stock_klines(codes: list[str], ktype: int = 2, limit: int = 120, region: str | None = None) -> dict[str, pd.DataFrame]:
    try:
        region_v = (region or ITICK_DEFAULT_REGION or "MY").strip().upper()
        norm_codes = []
        for c in codes or []:
            x = str(c or "").strip().upper()
            if x.endswith(".KL"):
                x = x[:-3]
            if x:
                norm_codes.append(x)
        norm_codes = sorted(set(norm_codes))
        if not norm_codes:
            return {}
        limit_i = int(limit) if limit is not None else 120
        if limit_i < 10:
            limit_i = 10
        if limit_i > 500:
            limit_i = 500
        ktype_i = int(ktype) if ktype is not None else 2
        if ktype_i not in {1, 2, 3, 4, 5, 8}:
            ktype_i = 2

        cache_key = f"{region_v}|{ktype_i}|{limit_i}|{','.join(norm_codes)}"
        now = time.time()
        hit = _ITICK_KLINE_CACHE.get(cache_key)
        if hit and (now - float(hit[0])) <= float(ITICK_CACHE_SECONDS):
            return hit[1]

        params = {"region": region_v, "codes": ",".join(norm_codes), "kType": str(ktype_i), "limit": str(limit_i)}
        j = _itick_get_json("/stock/klines", params)
        if not j:
            return {}
        data = j.get("data")
        if not isinstance(data, dict):
            return {}

        out: dict[str, pd.DataFrame] = {}
        for code, rows in data.items():
            if not isinstance(rows, list) or not rows:
                continue
            recs = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                t = r.get("t")
                if t is None:
                    continue
                try:
                    ts = pd.to_datetime(int(t), unit="ms", utc=True).tz_convert("Asia/Kuala_Lumpur")
                except Exception:
                    continue
                recs.append(
                    {
                        "Date": ts,
                        "Open": r.get("o"),
                        "High": r.get("h"),
                        "Low": r.get("l"),
                        "Close": r.get("c"),
                        "Volume": r.get("v"),
                    }
                )
            if not recs:
                continue
            df = pd.DataFrame(recs).set_index("Date").sort_index()
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["Close"])
            if df.empty:
                continue
            out[str(code).upper().strip()] = df

        _ITICK_KLINE_CACHE[cache_key] = (now, out)
        return out
    except Exception:
        return {}


def _itick_stock_name(code: str, region: str | None = None) -> str | None:
    try:
        token = _get_itick_token()
        if not token:
            return None
        c = str(code or "").strip().upper()
        if c.endswith(".KL"):
            c = c[:-3]
        if not c:
            return None
        region_v = (region or ITICK_DEFAULT_REGION or "MY").strip().upper()

        now = time.time()
        hit = _ITICK_INFO_CACHE.get(f"{region_v}:{c}")
        if hit and (now - float(hit[0])) <= float(ITICK_INFO_CACHE_SECONDS):
            return hit[1]

        j = _itick_get_json("/stock/info", {"type": "stock", "region": region_v, "code": c})
        if not j:
            return None
        data = j.get("data")
        if not isinstance(data, dict):
            return None
        name = data.get("n")
        if not name:
            return None
        name_s = str(name).strip()
        if not name_s:
            return None
        _ITICK_INFO_CACHE[f"{region_v}:{c}"] = (now, name_s)
        return name_s
    except Exception:
        return None


def _tradingview_last_price_cached_myr(symbol_path: str) -> float | None:
    try:
        key = str(symbol_path or "").strip()
        if not key:
            return None
        now = time.time()
        hit = _TV_PRICE_CACHE.get(key)
        if hit and (now - float(hit[0])) <= float(TRADINGVIEW_PRICE_CACHE_SECONDS):
            return float(hit[1])
        p = _tradingview_last_price_myr(key)
        if p is None:
            return None
        _TV_PRICE_CACHE[key] = (now, float(p))
        return float(p)
    except Exception:
        return None


def tradingview_last_price_for_ticker_myr(ticker: str) -> float | None:
    try:
        t = str(ticker or "").upper().strip()
        if not t:
            return None
        if t in {"FKLI=F", "FCPO=F"}:
            return None
        code = t.split(".")[0]
        if code.isdigit() and len(code) == 4:
            return _tradingview_last_price_cached_myr(f"MYX-{code}")
        return None
    except Exception:
        return None


def _synthetic_price_df(price: float, rows: int = 90):
    idx = pd.date_range(end=pd.Timestamp.now(tz="Asia/Kuala_Lumpur"), periods=rows, freq="B")
    df = pd.DataFrame(
        {
            "Open": price,
            "High": price,
            "Low": price,
            "Close": price,
            "Volume": 0,
        },
        index=idx,
    )
    return df


def get_stock_data(ticker, period="1y"):
    """
    Fetches historical stock data from Yahoo Finance.
    Handles alternative symbols for futures and prioritizes knowledge base names.
    """
    ticker = ticker.upper().strip()

    def _merge_intraday_daily(df: pd.DataFrame, stock_obj):
        try:
            intra = None
            for interval in ["5m", "15m", "30m", "60m"]:
                try:
                    intra = stock_obj.history(period="5d", interval=interval)
                    if intra is not None and not intra.empty:
                        break
                except Exception:
                    intra = None
            if intra is None or intra.empty:
                return df
            if not all(c in intra.columns for c in ["Open", "High", "Low", "Close", "Volume"]):
                return df
            if intra.index.tz is None:
                intra.index = intra.index.tz_localize("UTC")
            intra_kl = intra.copy()
            intra_kl.index = intra_kl.index.tz_convert("Asia/Kuala_Lumpur")
            day = intra_kl.index[-1].normalize()
            intra_day = intra_kl[intra_kl.index.normalize() == day]
            if intra_day is None or intra_day.empty:
                return df

            o = float(intra_day["Open"].iloc[0])
            h = float(pd.to_numeric(intra_day["High"], errors="coerce").max())
            l = float(pd.to_numeric(intra_day["Low"], errors="coerce").min())
            c = float(intra_day["Close"].iloc[-1])
            v = float(pd.to_numeric(intra_day["Volume"], errors="coerce").fillna(0).sum())
            if not all(x == x for x in [o, h, l, c]):
                return df

            ts = pd.Timestamp(day)
            if ts.tz is None:
                ts = ts.tz_localize("Asia/Kuala_Lumpur")
            else:
                ts = ts.tz_convert("Asia/Kuala_Lumpur")
            if df.index.tz is None:
                df = df.copy()
                df.index = df.index.tz_localize("Asia/Kuala_Lumpur")
            else:
                df = df.copy()
                df.index = df.index.tz_convert("Asia/Kuala_Lumpur")

            row = {
                "Open": o,
                "High": h,
                "Low": l,
                "Close": c,
                "Volume": v,
            }
            if "Dividends" in df.columns:
                row["Dividends"] = 0.0
            if "Stock Splits" in df.columns:
                row["Stock Splits"] = 0.0

            if ts in df.index:
                df.loc[ts, list(row.keys())] = list(row.values())
            else:
                df = pd.concat([df, pd.DataFrame([row], index=[ts])]).sort_index()
            return df
        except Exception:
            return df

    if ticker == "FKLI=F":
        df = None
        stock = None
        try:
            stock = yf.Ticker("^KLSE")
            df = stock.history(period=period)
            if df is not None and df.empty and period != "1mo":
                df = stock.history(period="1mo")
        except Exception:
            df = None

        if df is not None and not df.empty and stock is not None:
            df = _merge_intraday_daily(df, stock)
            price = _tradingview_last_price_myr("MYX-FKLI1!")
            if price is not None:
                try:
                    df = df.copy()
                    if "Close" in df.columns:
                        df.iloc[-1, df.columns.get_loc("Close")] = price
                    for c in ["Open", "High", "Low"]:
                        if c in df.columns and pd.isna(df[c].iloc[-1]):
                            df.iloc[-1, df.columns.get_loc(c)] = price
                except Exception:
                    pass
            return df, MARKET_INSIGHTS.get("FKLI=F", {}).get("name", "KLCI FUTURES")

        price = _tradingview_last_price_myr("MYX-FKLI1!")
        if price is not None:
            return _synthetic_price_df(price), MARKET_INSIGHTS.get("FKLI=F", {}).get("name", "KLCI FUTURES")

    if ticker == "FCPO=F":
        price = _tradingview_last_price_myr("MYX-FCPO1!")
        if price is not None:
            return _synthetic_price_df(price), MARKET_INSIGHTS.get("FCPO=F", {}).get("name", "CPO FUTURES")

    ALT_SYMBOLS = {
        "FKLI=F": ["^KLSE"],
        "FCPO=F": [],
        "FM70=F": ["FBM70.FGI"]
    }
    
    symbols_to_try = ALT_SYMBOLS.get(ticker, [ticker]) or [ticker]
    
    # Prioritize name from knowledge base
    base_name = ticker
    if ticker in MARKET_INSIGHTS:
        base_name = MARKET_INSIGHTS[ticker]['name']
    else:
        # Try matching by code (e.g. 6888)
        code = ticker.split(".")[0]
        for k, v in MARKET_INSIGHTS.items():
            if v.get('code') == code:
                base_name = v['name']
                break

    def _resolve_best_name() -> str:
        try:
            n = str(base_name or ticker)
            auto_name = _auto_universe_name(ticker)
            if auto_name:
                return str(auto_name)
            try:
                code2 = str(ticker).split(".")[0]
                it_name = _itick_stock_name(code2)
                if it_name:
                    return str(it_name)
            except Exception:
                pass
            return n
        except Exception:
            return str(base_name or ticker)

    mode = str(globals().get("PRICE_CACHE_MODE", "fast") or "fast").lower().strip()
    max_age = int(globals().get("PRICE_CACHE_MAX_AGE_SECONDS", 0) or 0)
    if mode in {"fast", "offline"}:
        cached_df, meta = _read_price_cache(ticker)
        if cached_df is not None and not cached_df.empty:
            if mode == "offline":
                return cached_df, _resolve_best_name()
            try:
                age_s = time.time() - float((meta or {}).get("mtime") or 0)
                if max_age <= 0 or age_s <= float(max_age):
                    if bool(globals().get("TRADINGVIEW_PRICE_OVERLAY_ENABLED")):
                        p = tradingview_last_price_for_ticker_myr(ticker)
                        if p is not None and "Close" in cached_df.columns:
                            try:
                                dfc = cached_df.copy()
                                dfc.iloc[-1, dfc.columns.get_loc("Close")] = float(p)
                                return dfc, base_name
                            except Exception:
                                pass
                    return cached_df, _resolve_best_name()
            except Exception:
                pass
    
    def _fetch_yahoo_chart(sym: str, rng: str, interval: str = "1d"):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
            params = {
                "range": rng,
                "interval": interval,
                "includePrePost": "false",
                "events": "div%7Csplit",
            }
            r = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=25,
            )
            if r.status_code != 200:
                return None
            j = r.json()
            result = (((j or {}).get("chart") or {}).get("result") or [None])[0]
            if not result:
                return None
            ts = result.get("timestamp") or []
            ind = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
            if not ts or not ind:
                return None
            df = pd.DataFrame(
                {
                    "Open": ind.get("open"),
                    "High": ind.get("high"),
                    "Low": ind.get("low"),
                    "Close": ind.get("close"),
                    "Volume": ind.get("volume"),
                },
                index=pd.to_datetime(ts, unit="s", utc=True),
            )
            df = df.dropna(subset=[c for c in ["Close"] if c in df.columns])
            if df.empty:
                return None
            try:
                df.index = df.index.tz_convert("Asia/Kuala_Lumpur")
            except Exception:
                pass
            return df
        except Exception:
            return None

    def _fetch_bursa_price_api(sym: str, outputsize: str = "compact"):
        try:
            base_url = os.environ.get("BURSA_PRICE_API_BASE_URL")
            api_key = os.environ.get("BURSA_PRICE_API_KEY")
            if not base_url or not api_key:
                return None

            symbol_raw = str(sym or "").strip().upper()
            if symbol_raw.endswith(".KL"):
                symbol_raw = symbol_raw[:-3]
            if symbol_raw.isdigit() and len(symbol_raw) == 4:
                symbol_try = symbol_raw
            else:
                symbol_try = symbol_raw

            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol_try,
                "outputsize": outputsize,
                "datatype": "json",
                "apikey": api_key,
            }
            r = requests.get(
                base_url,
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
                timeout=25,
            )
            if r.status_code != 200:
                return None
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
            if not isinstance(j, dict):
                return None

            ts = j.get("Time Series (Daily)") or j.get("TIME_SERIES_DAILY") or j.get("time_series_daily")
            if not isinstance(ts, dict) or not ts:
                return None

            rows = []
            for date_str, v in ts.items():
                if not isinstance(v, dict):
                    continue
                def _pick(*keys):
                    for k in keys:
                        if k in v and v[k] is not None:
                            return v[k]
                    return None

                o = _pick("1. open", "open", "o")
                h = _pick("2. high", "high", "h")
                l = _pick("3. low", "low", "l")
                c = _pick("4. close", "close", "c")
                vol = _pick("5. volume", "volume", "v")
                if c is None:
                    continue
                rows.append(
                    {
                        "Date": pd.to_datetime(date_str),
                        "Open": float(o) if o is not None else None,
                        "High": float(h) if h is not None else None,
                        "Low": float(l) if l is not None else None,
                        "Close": float(c) if c is not None else None,
                        "Volume": float(vol) if vol is not None else None,
                    }
                )
            if not rows:
                return None
            df = pd.DataFrame(rows).set_index("Date").sort_index()
            df = df.dropna(subset=["Close"])
            return df if not df.empty else None
        except Exception:
            return None

    period_map = {
        "1mo": "1mo",
        "3mo": "3mo",
        "6mo": "6mo",
        "1y": "1y",
        "2y": "2y",
        "5y": "5y",
        "10y": "10y",
        "max": "max",
    }
    rng = period_map.get(str(period).lower().strip(), "1y")

    for symbol in symbols_to_try:
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            if df.empty and period != "1mo":
                df = stock.history(period="1mo")
            
            if not df.empty:
                try:
                    if df.index.tz is None:
                        df = df.copy()
                        df.index = df.index.tz_localize("Asia/Kuala_Lumpur")
                    else:
                        df = df.copy()
                        df.index = df.index.tz_convert("Asia/Kuala_Lumpur")
                except Exception:
                    pass
                df = _merge_intraday_daily(df, stock)

                name = base_name
                # Only try yfinance info if we don't have a good name yet
                if name == ticker or ".KL" in str(name) or str(name).strip() == ticker.split(".")[0]:
                    try:
                        auto_name = _auto_universe_name(symbol) or _auto_universe_name(ticker)
                        if auto_name:
                            name = auto_name
                    except Exception:
                        pass
                if name == ticker or ".KL" in str(name):
                    try:
                        yf_info = stock.info
                        name = yf_info.get('shortName') or yf_info.get('longName') or name
                    except:
                        pass
                if name == ticker or ".KL" in str(name) or str(name).strip() == ticker.split(".")[0]:
                    try:
                        it_name = _itick_stock_name(ticker)
                        if it_name:
                            name = it_name
                    except Exception:
                        pass
                try:
                    _write_price_cache(ticker, df)
                except Exception:
                    pass

                if bool(globals().get("TRADINGVIEW_PRICE_OVERLAY_ENABLED")):
                    p = tradingview_last_price_for_ticker_myr(ticker)
                    if p is not None and "Close" in df.columns:
                        try:
                            df = df.copy()
                            df.iloc[-1, df.columns.get_loc("Close")] = float(p)
                        except Exception:
                            pass
                return df, name
        except Exception:
            continue

        try:
            df2 = _fetch_yahoo_chart(symbol, rng, interval="1d")
            if df2 is None and rng != "1mo":
                df2 = _fetch_yahoo_chart(symbol, "1mo", interval="1d")
            if df2 is not None and not df2.empty:
                name = base_name
                try:
                    auto_name = _auto_universe_name(symbol) or _auto_universe_name(ticker)
                    if auto_name:
                        name = auto_name
                except Exception:
                    pass
                if name == ticker or ".KL" in str(name) or str(name).strip() == ticker.split(".")[0]:
                    try:
                        it_name = _itick_stock_name(ticker)
                        if it_name:
                            name = it_name
                    except Exception:
                        pass
                try:
                    _write_price_cache(ticker, df2)
                except Exception:
                    pass

                if bool(globals().get("TRADINGVIEW_PRICE_OVERLAY_ENABLED")):
                    p = tradingview_last_price_for_ticker_myr(ticker)
                    if p is not None and "Close" in df2.columns:
                        try:
                            df2 = df2.copy()
                            df2.iloc[-1, df2.columns.get_loc("Close")] = float(p)
                        except Exception:
                            pass
                return df2, name
        except Exception:
            pass

        try:
            df3 = _fetch_bursa_price_api(symbol, outputsize="compact")
            if df3 is None and str(period).lower().strip() in {"2y", "5y", "10y", "max"}:
                df3 = _fetch_bursa_price_api(symbol, outputsize="full")
            if df3 is not None and not df3.empty:
                name = base_name
                try:
                    auto_name = _auto_universe_name(symbol) or _auto_universe_name(ticker)
                    if auto_name:
                        name = auto_name
                except Exception:
                    pass
                if name == ticker or ".KL" in str(name) or str(name).strip() == ticker.split(".")[0]:
                    try:
                        it_name = _itick_stock_name(ticker)
                        if it_name:
                            name = it_name
                    except Exception:
                        pass
                try:
                    _write_price_cache(ticker, df3)
                except Exception:
                    pass

                if bool(globals().get("TRADINGVIEW_PRICE_OVERLAY_ENABLED")):
                    p = tradingview_last_price_for_ticker_myr(ticker)
                    if p is not None and "Close" in df3.columns:
                        try:
                            df3 = df3.copy()
                            df3.iloc[-1, df3.columns.get_loc("Close")] = float(p)
                        except Exception:
                            pass
                return df3, name
        except Exception:
            pass

    cached_df, _ = _read_price_cache(ticker)
    if cached_df is not None and not cached_df.empty:
        return cached_df, _resolve_best_name()
    return None, base_name

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

def _resolve_insight(ticker: str, resolved_name: str | None):
    t = str(ticker).upper().strip()
    code = t.split(".")[0]
    analysis = "Technical breakout analysis based on live data."
    catalyst = "Market momentum / Trend following."

    insight = MARKET_INSIGHTS.get(t)
    if not insight:
        for _, v in MARKET_INSIGHTS.items():
            if v.get("code") == code:
                insight = v
                break

    if insight:
        name = insight["name"]
        code = insight["code"]
        analysis = insight["analysis"]
        catalyst = insight["catalyst"]
    else:
        name = resolved_name or code
        try:
            if str(name).strip().upper() in {t, code, f"{code}.KL"} or ".KL" in str(name).upper():
                auto_name = _auto_universe_name(t) or _auto_universe_name(f"{code}.KL")
                if auto_name:
                    name = auto_name
        except Exception:
            pass

    if name == t or name == code or ".KL" in str(name):
        name = str(name).replace(".KL", "").strip()

    if str(name).strip() == code:
        try:
            it_name = _itick_stock_name(code)
            if it_name:
                name = it_name
        except Exception:
            pass

    return code, name, analysis, catalyst


def _resolve_insight_v3(ticker: str, resolved_name: str | None):
    t = str(ticker).upper().strip()
    code = t.split(".")[0]
    analysis = "Technical breakout analysis based on live data."
    catalyst = "Market momentum / Trend following."
    sector = "Unknown"

    insight = MARKET_INSIGHTS.get(t)
    if not insight:
        for _, v in MARKET_INSIGHTS.items():
            if v.get("code") == code:
                insight = v
                break

    if insight:
        name = insight["name"]
        code = insight["code"]
        analysis = insight["analysis"]
        catalyst = insight["catalyst"]
        sector = str(insight.get("sector") or sector).strip() or sector
    else:
        name = resolved_name or code
        try:
            if str(name).strip().upper() in {t, code, f"{code}.KL"} or ".KL" in str(name).upper():
                auto_name = _auto_universe_name(t) or _auto_universe_name(f"{code}.KL")
                if auto_name:
                    name = auto_name
        except Exception:
            pass

    if name == t or name == code or ".KL" in str(name):
        name = str(name).replace(".KL", "").strip()

    if str(name).strip() == code:
        try:
            it_name = _itick_stock_name(code)
            if it_name:
                name = it_name
        except Exception:
            pass

    return code, name, sector, analysis, catalyst

def analyze_breakout(ticker, df, resolved_name=None, min_rows=50):
    """
    Performs technical breakout analysis.
    Returns a dictionary with results.
    """
    if df is None or len(df) < min_rows:
        return None

    if len(df) >= 2:
        try:
            last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
            last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
            if (pd.isna(last_close) or pd.isna(last_open)):
                df = df.iloc[:-1]
            elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0 and not _is_today_kl(df.index[-1]):
                df = df.iloc[:-1]
        except Exception:
            pass

    if df is None or len(df) < min_rows:
        return None

    ticker = ticker.upper().strip()
    current_price = df['Close'].iloc[-1]
    
    # Technical Indicators (Safe checks for short data)
    try:
        sma_20 = SMAIndicator(df['Close'], window=20).sma_indicator().iloc[-1]
        sma_50 = SMAIndicator(df['Close'], window=50).sma_indicator().iloc[-1]
        rsi = RSIIndicator(df['Close'], window=14).rsi().iloc[-1]
        if pd.isna(rsi):
            rsi = 50.0
        
        # Breakout Logic
        avg_volume_20 = df['Volume'].rolling(window=20).mean().iloc[-1]
        current_volume = df['Volume'].iloc[-1]
        
        is_above_sma = current_price > sma_20 and current_price > sma_50
        is_volume_surge = current_volume > (avg_volume_20 * 1.5)
        is_price_break = current_price > df['Close'].iloc[-20:-1].max() # 20-day high
        
        # Scoring
        score = 0
        if is_above_sma: score += 1
        if is_volume_surge: score += 2
        if is_price_break: score += 2
    except:
        # Fallback for very short data (e.g. newly listed or restricted history)
        rsi = 50.0
        score = 1
        is_volume_surge = False
    
    code, name, analysis, catalyst = _resolve_insight(ticker, resolved_name)
    
    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "price": float(round(float(current_price), 3)),
        "rsi": float(round(float(rsi), 2)),
        "volume_surge": bool(is_volume_surge),
        "score": score,
        "analysis": analysis,
        "catalyst": catalyst
    }

def analyze_breakout_v2(ticker, df, resolved_name=None, benchmark_df=None, min_rows=120):
    if df is None or len(df) < min_rows:
        return None

    if len(df) >= 2:
        try:
            last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
            last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
            if (pd.isna(last_close) or pd.isna(last_open)):
                df = df.iloc[:-1]
            elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0 and not _is_today_kl(df.index[-1]):
                df = df.iloc[:-1]
        except Exception:
            pass

    if df is None or len(df) < min_rows:
        return None

    ticker = str(ticker).upper().strip()
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    try:
        current_close = float(df["Close"].iloc[-1])
        if not (current_close > 0.0):
            return None
    except Exception:
        return None

    rsi = 50.0
    try:
        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
        if rsi_v == rsi_v:
            rsi = float(rsi_v)
    except Exception:
        pass

    sma20 = sma50 = sma200 = None
    try:
        sma20 = float(SMAIndicator(df["Close"], window=20).sma_indicator().iloc[-1])
        sma50 = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-1])
        if len(df) >= 220:
            sma200 = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-1])
    except Exception:
        pass

    score = 0
    score_max = 10

    try:
        if sma50 is not None and current_close > sma50:
            sma50_prev = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-6])
            if sma50_prev == sma50_prev and sma50 > sma50_prev:
                score += 2
    except Exception:
        pass

    try:
        if sma200 is not None and current_close > sma200:
            sma200_prev = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-6])
            if sma200_prev == sma200_prev and sma200 > sma200_prev:
                score += 2
    except Exception:
        pass

    breakout_lookback = 55
    try:
        if len(df) >= breakout_lookback + 5:
            prior_high = float(df["Close"].iloc[-breakout_lookback:-1].max())
            if current_close > prior_high:
                score += 2
    except Exception:
        pass

    try:
        o = float(df["Open"].iloc[-1])
        h = float(df["High"].iloc[-1])
        l = float(df["Low"].iloc[-1])
        if h > l:
            close_pos = (current_close - l) / (h - l)
            if close_pos >= 0.7:
                score += 1
    except Exception:
        pass

    try:
        if "Volume" in df.columns and len(df) >= 30:
            current_vol = float(df["Volume"].iloc[-1])
            avg_vol20 = float(df["Volume"].rolling(window=20).mean().iloc[-1])
            if avg_vol20 > 0 and current_vol >= avg_vol20 * 1.8:
                score += 1
            traded_value20 = float((df["Close"] * df["Volume"]).rolling(window=20).mean().iloc[-1])
            if traded_value20 >= 1_000_000:
                score += 1
    except Exception:
        pass

    rs_3m = None
    try:
        if benchmark_df is not None and not benchmark_df.empty:
            s = df["Close"].copy()
            b = benchmark_df["Close"].copy() if "Close" in benchmark_df.columns else None
            if b is not None:
                join = pd.concat([s, b], axis=1, join="inner").dropna()
                if len(join) >= 70:
                    s_now = float(join.iloc[-1, 0])
                    s_prev = float(join.iloc[-64, 0])
                    b_now = float(join.iloc[-1, 1])
                    b_prev = float(join.iloc[-64, 1])
                    if s_prev > 0 and b_prev > 0:
                        rs_3m = (s_now / s_prev) - (b_now / b_prev)
                        if rs_3m > 0:
                            score += 1
    except Exception:
        pass

    atr_contraction = False
    try:
        if len(df) >= 40:
            prev_close = df["Close"].shift(1)
            tr = pd.concat(
                [
                    (df["High"] - df["Low"]).abs(),
                    (df["High"] - prev_close).abs(),
                    (df["Low"] - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr14 = tr.rolling(window=14).mean()
            atr_pct = atr14 / df["Close"]
            recent = float(pd.to_numeric(atr_pct.tail(5), errors="coerce").dropna().mean())
            prior = float(pd.to_numeric(atr_pct.iloc[-25:-5], errors="coerce").dropna().mean())
            if prior > 0 and recent > 0 and recent <= prior * 0.8:
                atr_contraction = True
                score += 1
    except Exception:
        pass

    code, name, analysis, catalyst = _resolve_insight(ticker, resolved_name)

    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "price": float(round(float(current_close), 3)),
        "rsi": float(round(float(rsi), 2)),
        "score": int(score),
        "score_max": int(score_max),
        "analysis": analysis,
        "catalyst": catalyst,
        "rs_3m": None if rs_3m is None else float(rs_3m),
        "atr_contraction": bool(atr_contraction),
        "model": "v2",
    }


def analyze_breakout_v3(ticker, df, resolved_name=None, benchmark_df=None, min_rows=120, signal_lookback=5, max_runup_pct=None, max_pullback_pct=None, retest_days=0):
    if df is None or len(df) < min_rows:
        return None

    if len(df) >= 2:
        try:
            last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
            last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
            if (pd.isna(last_close) or pd.isna(last_open)):
                df = df.iloc[:-1]
            elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0 and not _is_today_kl(df.index[-1]):
                df = df.iloc[:-1]
        except Exception:
            pass

    if df is None or len(df) < min_rows:
        return None

    ticker = str(ticker).upper().strip()
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    try:
        current_close = float(df["Close"].iloc[-1])
        if not (current_close > 0.0):
            return None
    except Exception:
        return None

    rsi = 50.0
    try:
        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
        if rsi_v == rsi_v:
            rsi = float(rsi_v)
    except Exception:
        pass

    sma50 = sma200 = None
    sma50_series = None
    try:
        sma50_series = SMAIndicator(df["Close"], window=50).sma_indicator()
        sma50 = float(sma50_series.iloc[-1])
        if len(df) >= 220:
            sma200 = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-1])
    except Exception:
        pass

    score = 0
    score_max = 11

    try:
        if sma50 is not None and current_close > sma50:
            sma50_prev = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-6])
            if sma50_prev == sma50_prev and sma50 > sma50_prev:
                score += 2
    except Exception:
        pass

    try:
        if sma200 is not None and current_close > sma200:
            sma200_prev = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-6])
            if sma200_prev == sma200_prev and sma200 > sma200_prev:
                score += 2
    except Exception:
        pass

    breakout_lookback = 55

    breakout_candle = False
    breakout_candle_valid = False
    breakout_hold_ok = False
    breakout_55 = False
    power_candle = False
    volume_spike = False
    breakout_candle_ts = None
    breakout_candle_close = None
    breakout_candle_vol = None

    liquidity_ok = False
    try:
        if "Volume" in df.columns and len(df) >= 30:
            traded_value20 = float((df["Close"] * df["Volume"]).rolling(window=20).mean().shift(1).iloc[-1])
            if traded_value20 >= 1_000_000:
                liquidity_ok = True
                score += 1
    except Exception:
        pass

    try:
        lookback_days = int(signal_lookback) if signal_lookback is not None else 5
    except Exception:
        lookback_days = 5
    if lookback_days < 1:
        lookback_days = 1
    if lookback_days > 20:
        lookback_days = 20

    try:
        if "Volume" in df.columns and len(df) >= (breakout_lookback + lookback_days + 1):
            vols = pd.to_numeric(df["Volume"], errors="coerce")
            avg20_prev = vols.rolling(window=20).mean().shift(1)

            start_idx = len(df) - lookback_days
            for i in range(len(df) - 1, start_idx - 1, -1):
                if i < breakout_lookback or i < 20:
                    continue
                close_i = float(df["Close"].iloc[i])
                open_i = float(df["Open"].iloc[i])
                high_i = float(df["High"].iloc[i])
                low_i = float(df["Low"].iloc[i])
                if not (close_i > 0.0):
                    continue

                prior_close_high = float(df["Close"].iloc[i - breakout_lookback : i].max())
                is_breakout_55 = close_i > prior_close_high
                if not is_breakout_55:
                    continue

                if sma50_series is not None:
                    try:
                        sma50_i = float(sma50_series.iloc[i])
                        if sma50_i == sma50_i and not (close_i > sma50_i):
                            continue
                    except Exception:
                        pass

                is_power = False
                try:
                    if high_i > low_i:
                        close_pos = (close_i - low_i) / (high_i - low_i)
                        body_pct = abs(close_i - open_i) / (high_i - low_i)
                        if close_i > open_i and close_pos >= 0.7 and body_pct >= 0.55:
                            is_power = True
                except Exception:
                    is_power = False
                if not is_power:
                    continue

                is_vol_spike = False
                try:
                    avg_i = float(avg20_prev.iloc[i])
                    vol_i = float(vols.iloc[i])
                    if avg_i > 0 and vol_i >= avg_i * 1.8:
                        is_vol_spike = True
                except Exception:
                    is_vol_spike = False
                if not is_vol_spike:
                    continue

                breakout_candle = True
                breakout_55 = True
                power_candle = True
                volume_spike = True
                breakout_candle_ts = df.index[i]
                breakout_candle_close = close_i
                try:
                    breakout_candle_vol = float(vols.iloc[i])
                except Exception:
                    breakout_candle_vol = None
                break
    except Exception:
        pass

    runup_pct = None
    try:
        if breakout_candle and breakout_candle_close is not None and breakout_candle_close > 0:
            runup_pct = ((float(current_close) / float(breakout_candle_close)) - 1.0) * 100.0
    except Exception:
        runup_pct = None

    max_runup_val = None
    try:
        if max_runup_pct is not None and str(max_runup_pct).strip() != "":
            max_runup_val = float(max_runup_pct)
    except Exception:
        max_runup_val = None

    max_pullback_val = None
    try:
        if max_pullback_pct is not None and str(max_pullback_pct).strip() != "":
            max_pullback_val = float(max_pullback_pct)
    except Exception:
        max_pullback_val = None

    if breakout_candle:
        if max_pullback_val is None or (runup_pct is not None and runup_pct >= -max_pullback_val):
            breakout_hold_ok = True

    if breakout_candle:
        if breakout_hold_ok and (max_runup_val is None or (runup_pct is not None and runup_pct <= max_runup_val)):
            breakout_candle_valid = True
            score += 1
    else:
        try:
            if len(df) >= breakout_lookback + 5:
                prior_high = float(df["Close"].iloc[-breakout_lookback:-1].max())
                if current_close > prior_high:
                    breakout_55 = True
                    score += 2
        except Exception:
            pass

        try:
            o = float(df["Open"].iloc[-1])
            h = float(df["High"].iloc[-1])
            l = float(df["Low"].iloc[-1])
            if h > l:
                close_pos = (current_close - l) / (h - l)
                if close_pos >= 0.7:
                    score += 1
        except Exception:
            pass

        try:
            if "Volume" in df.columns and len(df) >= 30:
                current_vol = float(df["Volume"].iloc[-1])
                avg_vol20 = float(df["Volume"].rolling(window=20).mean().shift(1).iloc[-1])
                if avg_vol20 > 0 and current_vol >= avg_vol20 * 1.8:
                    score += 1
        except Exception:
            pass

    rs_3m = None
    try:
        if benchmark_df is not None and not benchmark_df.empty:
            s = df["Close"].copy()
            b = benchmark_df["Close"].copy() if "Close" in benchmark_df.columns else None
            if b is not None:
                join = pd.concat([s, b], axis=1, join="inner").dropna()
                if len(join) >= 70:
                    s_now = float(join.iloc[-1, 0])
                    s_prev = float(join.iloc[-64, 0])
                    b_now = float(join.iloc[-1, 1])
                    b_prev = float(join.iloc[-64, 1])
                    if s_prev > 0 and b_prev > 0:
                        rs_3m = (s_now / s_prev) - (b_now / b_prev)
                        if rs_3m > 0:
                            score += 1
    except Exception:
        pass

    atr_contraction = False
    try:
        if len(df) >= 40:
            prev_close = df["Close"].shift(1)
            tr = pd.concat(
                [
                    (df["High"] - df["Low"]).abs(),
                    (df["High"] - prev_close).abs(),
                    (df["Low"] - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr14 = tr.rolling(window=14).mean()
            atr_pct = atr14 / df["Close"]
            recent = float(pd.to_numeric(atr_pct.tail(5), errors="coerce").dropna().mean())
            prior = float(pd.to_numeric(atr_pct.iloc[-25:-5], errors="coerce").dropna().mean())
            if prior > 0 and recent > 0 and recent <= prior * 0.8:
                atr_contraction = True
                score += 1
    except Exception:
        pass

    code, name, sector, analysis, catalyst = _resolve_insight_v3(ticker, resolved_name)

    breakout_candle_date = None
    breakout_candle_age = None
    if breakout_candle_ts is not None:
        try:
            breakout_candle_date = pd.Timestamp(breakout_candle_ts).date().isoformat()
            breakout_candle_age = int(len(df) - 1 - df.index.get_loc(breakout_candle_ts))
        except Exception:
            breakout_candle_date = None
            breakout_candle_age = None

    retest_days_i = 0
    try:
        retest_days_i = int(retest_days) if retest_days is not None else 0
    except Exception:
        retest_days_i = 0
    if retest_days_i < 0:
        retest_days_i = 0
    if retest_days_i > 20:
        retest_days_i = 20

    retest_confirmed = False
    retest_touch_ts = None
    retest_vol_ok = None
    if breakout_candle and breakout_candle_ts is not None and breakout_candle_close is not None and retest_days_i > 0:
        try:
            i0 = int(df.index.get_loc(breakout_candle_ts))
            i1 = min(len(df) - 1, i0 + retest_days_i)
            if i1 >= i0 + 1:
                level = float(breakout_candle_close)
                hold_pct = 0.0 if max_pullback_val is None else float(max_pullback_val)
                hold_floor = level * (1.0 - (hold_pct / 100.0))
                touch_ceiling = level * 1.01
                for j in range(i0 + 1, i1 + 1):
                    low_j = float(df["Low"].iloc[j])
                    close_j = float(df["Close"].iloc[j])
                    if low_j <= touch_ceiling and close_j >= hold_floor:
                        retest_touch_ts = df.index[j]
                        if breakout_candle_vol is not None:
                            try:
                                vj = float(df["Volume"].iloc[j])
                                retest_vol_ok = bool(vj <= breakout_candle_vol * 0.9)
                            except Exception:
                                retest_vol_ok = None
                        retest_confirmed = True if (retest_vol_ok is None or retest_vol_ok) else False
                        break
        except Exception:
            retest_confirmed = False

    retest_touch_date = None
    if retest_touch_ts is not None:
        try:
            retest_touch_date = pd.Timestamp(retest_touch_ts).date().isoformat()
        except Exception:
            retest_touch_date = None

    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "sector": sector,
        "price": float(round(float(current_close), 3)),
        "rsi": float(round(float(rsi), 2)),
        "score": int(score),
        "score_max": int(score_max),
        "analysis": analysis,
        "catalyst": catalyst,
        "rs_3m": None if rs_3m is None else float(rs_3m),
        "atr_contraction": bool(atr_contraction),
        "breakout_55": bool(breakout_55),
        "power_candle": bool(power_candle),
        "volume_spike": bool(volume_spike),
        "liquidity_ok": bool(liquidity_ok),
        "breakout_candle": bool(breakout_candle),
        "breakout_candle_valid": bool(breakout_candle_valid),
        "breakout_hold_ok": bool(breakout_hold_ok),
        "breakout_candle_date": breakout_candle_date,
        "breakout_candle_age": breakout_candle_age,
        "signal_lookback": int(lookback_days),
        "breakout_candle_close": None if breakout_candle_close is None else float(breakout_candle_close),
        "breakout_candle_vol": None if breakout_candle_vol is None else float(breakout_candle_vol),
        "runup_pct": None if runup_pct is None else float(runup_pct),
        "max_runup_pct": None if max_runup_val is None else float(max_runup_val),
        "max_pullback_pct": None if max_pullback_val is None else float(max_pullback_val),
        "retest_days": int(retest_days_i),
        "retest_confirmed": bool(retest_confirmed),
        "retest_touch_date": retest_touch_date,
        "retest_vol_ok": None if retest_vol_ok is None else bool(retest_vol_ok),
        "model": "v3",
    }


def analyze_breakout_v3_intraday(ticker: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame, resolved_name: str | None = None, max_runup_pct: float | None = 5.0, min_intraday_bars: int = 40, lookback_bars: int | None = 60):
    if daily_df is None or daily_df.empty or intraday_df is None or intraday_df.empty:
        return None

    try:
        if len(intraday_df) < int(min_intraday_bars):
            return None
    except Exception:
        return None

    ticker = str(ticker or "").upper().strip()
    df_d = daily_df.copy()
    df_i = intraday_df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df_d.columns:
            df_d[c] = pd.to_numeric(df_d[c], errors="coerce")
        if c in df_i.columns:
            df_i[c] = pd.to_numeric(df_i[c], errors="coerce")
    df_d = df_d.dropna(subset=["Close"]).copy()
    df_i = df_i.dropna(subset=["Close"]).copy()
    if df_d.empty or df_i.empty:
        return None

    breakout_lookback = 55
    if len(df_d) < breakout_lookback + 5:
        return None
    try:
        breakout_level = float(df_d["Close"].iloc[-breakout_lookback:-1].max())
        if not (breakout_level > 0.0):
            return None
    except Exception:
        return None

    max_run = None
    try:
        if max_runup_pct is not None and str(max_runup_pct).strip() != "":
            max_run = float(max_runup_pct)
    except Exception:
        max_run = None

    try:
        n = int(lookback_bars) if lookback_bars is not None else 60
        if n < 10:
            n = 10
        if n > len(df_i):
            n = len(df_i)
        df_scan = df_i.tail(n).copy()
    except Exception:
        return None

    vol_avg_prev = None
    try:
        if "Volume" in df_scan.columns:
            vols = pd.to_numeric(df_scan["Volume"], errors="coerce")
            vol_avg_prev = vols.rolling(window=20).mean().shift(1)
    except Exception:
        vol_avg_prev = None

    best = None
    best_score = None
    for ts, row in df_scan.iterrows():
        try:
            o = float(row["Open"])
            h = float(row["High"])
            l = float(row["Low"])
            c = float(row["Close"])
        except Exception:
            continue
        if not (c > 0.0):
            continue
        if not (c > breakout_level):
            continue

        runup_pct = ((c / breakout_level) - 1.0) * 100.0
        if max_run is not None:
            try:
                if float(runup_pct) > float(max_run):
                    continue
            except Exception:
                pass

        power_candle = False
        try:
            if h > l:
                close_pos = (c - l) / (h - l)
                body_pct = abs(c - o) / (h - l)
                if c > o and close_pos >= 0.6 and body_pct >= 0.4:
                    power_candle = True
        except Exception:
            power_candle = False

        volume_spike = False
        v = 0.0
        try:
            if "Volume" in row and row.get("Volume") is not None:
                v = float(row.get("Volume") or 0.0)
        except Exception:
            v = 0.0
        try:
            if vol_avg_prev is not None:
                avg20_prev = vol_avg_prev.loc[ts]
                if avg20_prev is not None and not pd.isna(avg20_prev):
                    a = float(avg20_prev)
                    if a > 0.0 and v >= a * 1.5:
                        volume_spike = True
        except Exception:
            volume_spike = False

        if not (power_candle or volume_spike):
            continue

        score = 0.0
        score += 2.0 if power_candle else 0.0
        score += 2.0 if volume_spike else 0.0
        try:
            score += max(0.0, 2.0 - float(runup_pct) / 2.5)
        except Exception:
            pass

        if best_score is None or score > float(best_score):
            best_score = float(score)
            best = {
                "ts": ts,
                "close": float(c),
                "runup_pct": float(runup_pct),
                "power_candle": bool(power_candle),
                "volume_spike": bool(volume_spike),
            }

    if not best:
        return None

    c = float(best["close"])
    ts = best["ts"]
    runup_pct = float(best["runup_pct"])
    power_candle = bool(best["power_candle"])
    volume_spike = bool(best["volume_spike"])

    code, name, sector, analysis, catalyst = _resolve_insight_v3(ticker, resolved_name)
    score = 0
    score_max = 7
    score += 2 if power_candle else 0
    score += 2 if volume_spike else 0
    score += 1
    score += 1 if max_run is None or runup_pct <= max_run else 0
    score += 1

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "price": float(c),
        "rsi": 50.0,
        "score": int(score),
        "score_max": int(score_max),
        "breakout_55": True,
        "breakout_candle": True,
        "breakout_candle_valid": True,
        "breakout_hold_ok": True,
        "runup_pct": float(runup_pct),
        "max_runup_pct": None if max_run is None else float(max_run),
        "max_pullback_pct": None,
        "retest_days": 0,
        "retest_confirmed": False,
        "breakout_candle_date": pd.Timestamp(ts).date().isoformat(),
        "breakout_candle_age": 0,
        "breakout_level": float(breakout_level),
        "power_candle": bool(power_candle),
        "volume_spike": bool(volume_spike),
        "liquidity_ok": True,
        "analysis": analysis,
        "catalyst": catalyst,
        "model": "v3i",
    }

# --- KLCI COMPONENTS (Top 30 Stocks) ---
KLCI_COMPONENTS = [
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5183.KL", 
    "5225.KL", "6947.KL", "6888.KL", "6012.KL", "5819.KL",
    "8869.KL", "6033.KL", "3816.KL", "1066.KL", "4707.KL",
    "1961.KL", "2445.KL", "4065.KL", "3182.KL", "4715.KL",
    "7277.KL", "4197.KL", "5285.KL", "5681.KL", "1015.KL",
    "1082.KL", "0166.KL", "5296.KL", "5246.KL", "4677.KL"
]

KLCI_AUTO_UPDATE_ENABLED = True
KLCI_COMPONENTS_AUTO_FILE = os.path.join(os.path.dirname(__file__), "klci_components_auto.txt")

INDEX_AUTO_UPDATE_ENABLED = True
INDEX_FORCE_REFRESH = False
INDEX_COMPONENTS_CACHE_DIR = os.path.join(os.path.dirname(__file__), "index_components_cache")
try:
    os.makedirs(INDEX_COMPONENTS_CACHE_DIR, exist_ok=True)
except Exception:
    pass

PRICE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "price_cache")
PRICE_CACHE_MODE = "fast"  # fast|latest|offline
PRICE_CACHE_MAX_AGE_SECONDS = 15 * 60
try:
    os.makedirs(PRICE_CACHE_DIR, exist_ok=True)
except Exception:
    pass


def _price_cache_path(ticker: str) -> str:
    safe = re.sub(r"[^A-Z0-9._-]+", "_", str(ticker or "").upper())
    return os.path.join(PRICE_CACHE_DIR, f"{safe}.csv")


def _read_price_cache(ticker: str) -> tuple[pd.DataFrame | None, dict | None]:
    try:
        path = _price_cache_path(ticker)
        if not os.path.exists(path):
            return None, None
        df = pd.read_csv(path)
        if "Date" not in df.columns:
            return None, None
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
        meta = {"path": path, "mtime": os.path.getmtime(path)}
        return df, meta
    except Exception:
        return None, None


def _write_price_cache(ticker: str, df: pd.DataFrame) -> None:
    try:
        if df is None or df.empty:
            return
        path = _price_cache_path(ticker)
        out = df.copy()
        out = out[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in out.columns]]
        out = out.dropna(subset=["Close"]).tail(2000)
        out = out.reset_index().rename(columns={out.index.name or "index": "Date"})
        out.to_csv(path, index=False)
    except Exception:
        return


def _read_text_lines(path: str) -> list[str]:
    try:
        if not path or not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f.readlines()]
    except Exception:
        return []


def _write_text_lines(path: str, lines: list[str]) -> bool:
    try:
        if not path:
            return False
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{line}\n")
        return True
    except Exception:
        return False


def _normalize_kl_ticker(x: str) -> str | None:
    try:
        s = str(x).strip().upper()
        if not s:
            return None
        s = s.replace(" ", "")
        if s.endswith(".KL"):
            s = s[:-3]
        if s.isdigit() and len(s) == 4:
            return f"{s}.KL"
        return None
    except Exception:
        return None


def _normalize_bm_code(x: str) -> str | None:
    try:
        s = str(x).strip().upper().replace(" ", "")
        if not s:
            return None
        if s.endswith(".KL"):
            s = s[:-3]
        if s.isdigit() and len(s) == 4:
            return s
        return None
    except Exception:
        return None


def _extract_kl_codes_from_text(text: str) -> list[str]:
    try:
        if not text:
            return []
        codes = re.findall(r"\b(\d{4})\.KL\b", text.upper())
        return sorted({f"{c}.KL" for c in codes})
    except Exception:
        return []


def _resolve_tradingview_symbol_to_kl(ticker_symbol: str, company_name: str | None = None) -> str | None:
    try:
        sym = str(ticker_symbol or "").strip().upper()
        if not sym:
            return None
        code = _normalize_bm_code(sym)
        if code:
            return f"{code}.KL"

        if company_name:
            m = _best_ticker_match_by_name(company_name)
            if m:
                return m

        t = search_bursa(sym)
        if t:
            return t
        if company_name:
            t = search_bursa(company_name)
            if t:
                return t
        return None
    except Exception:
        return None


def _fetch_investingmalaysia_index_tickers(slug: str, max_pages: int = 12, max_seconds: float = 25.0) -> list[str]:
    try:
        t0 = time.time() if 'time' in globals() else None
        base = f"https://investingmalaysia.com/category/ftse-bursa-malaysia-index/{slug}/"
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
        all_codes = set()
        for p in range(1, int(max_pages) + 1):
            if t0 is not None and (time.time() - t0) > float(max_seconds):
                break
            url = base if p == 1 else base + f"page/{p}/"
            try:
                r = requests.get(url, headers=headers, timeout=25)
                if r.status_code != 200:
                    break
                html = r.text or ""
            except Exception:
                break

            found = set(re.findall(r"/stock/[^/]+-(\d{4})/", html))
            if not found:
                break
            before = len(all_codes)
            all_codes |= found
            if len(all_codes) == before:
                break
        tickers = sorted({f"{c}.KL" for c in all_codes if c and str(c).isdigit() and len(str(c)) == 4})
        return tickers
    except Exception:
        return []


def refresh_index_components(index_key: str, force: bool = False, max_age_days: int = 30, allow_network: bool = True) -> tuple[list[str], str]:
    key = str(index_key or "").lower().strip()
    defs = {
        "fbm70": {
            "slug": "fbm-mid-70",
            "min": 50,
            "max": 130,
            "pages": 8,
        },
        "fbm100": {
            "slug": "fbm-top-100",
            "min": 70,
            "max": 160,
            "pages": 8,
        },
        "smallcap": {
            "slug": "fbm-small-cap",
            "min": 50,
            "max": 400,
            "pages": 10,
        },
    }
    if key not in defs:
        return [], "unknown"

    cache_file = os.path.join(INDEX_COMPONENTS_CACHE_DIR, f"{key}.txt")

    cached_any = []
    if os.path.exists(cache_file):
        try:
            cached_any = [_normalize_kl_ticker(x) for x in _read_text_lines(cache_file)]
            cached_any = sorted({x for x in cached_any if x})
            if not (defs[key]["min"] <= len(cached_any) <= defs[key]["max"]):
                cached_any = []
        except Exception:
            cached_any = []

    try:
        if not bool(allow_network):
            if cached_any:
                return cached_any, "cache"
            return [], "cache-missing"
    except Exception:
        if cached_any:
            return cached_any, "cache"
        return [], "cache-missing"

    try:
        if not force and os.path.exists(cache_file):
            try:
                age_s = (pd.Timestamp.now() - pd.Timestamp.fromtimestamp(os.path.getmtime(cache_file))).total_seconds()
                if age_s < float(max_age_days) * 86400.0:
                    cached = [_normalize_kl_ticker(x) for x in _read_text_lines(cache_file)]
                    cached = sorted({x for x in cached if x})
                    if defs[key]["min"] <= len(cached) <= defs[key]["max"]:
                        return cached, "cache"
            except Exception:
                pass

        resolved = _fetch_investingmalaysia_index_tickers(defs[key]["slug"], max_pages=int(defs[key].get("pages") or 10), max_seconds=25.0)
        resolved = sorted({_normalize_kl_ticker(x) for x in resolved if _normalize_kl_ticker(x)})
        if defs[key]["min"] <= len(resolved) <= defs[key]["max"]:
            _write_text_lines(cache_file, [t.replace(".KL", "") for t in resolved])
            return resolved, "investingmalaysia"
        if cached_any:
            return cached_any, "cache-fallback"
        return [], "investingmalaysia"
    except Exception:
        if cached_any:
            return cached_any, "cache-fallback"
        return [], "error"


def get_index_components_info(index_key: str, max_age_days: int = 30) -> dict:
    key = str(index_key or "").lower().strip()
    cache_file = os.path.join(INDEX_COMPONENTS_CACHE_DIR, f"{key}.txt")
    try:
        tickers, src = refresh_index_components(key, force=False, max_age_days=max_age_days, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        updated = None
        if os.path.exists(cache_file):
            try:
                updated = pd.Timestamp.fromtimestamp(os.path.getmtime(cache_file)).isoformat()
            except Exception:
                updated = None
        return {"tickers": tickers, "source": src, "updated_at": updated}
    except Exception:
        return {"tickers": [], "source": "error", "updated_at": None}


def _find_tickers_by_name_keywords(keywords: list[str], max_hits: int = 80) -> list[str]:
    out = []
    try:
        kw = [str(k).strip().upper() for k in (keywords or []) if str(k).strip()]
        if not kw:
            return []

        kw_items = []
        for k in kw:
            toks = _name_tokens(k)
            kw_items.append((k, toks))

        def _match(name: str) -> bool:
            name_u = str(name or "").upper()
            name_toks = _name_tokens(name_u)
            for raw, toks in kw_items:
                if len(raw) <= 3:
                    if raw in name_toks:
                        return True
                    continue
                if toks and toks.issubset(name_toks):
                    return True
                if raw and raw in name_u:
                    return True
            return False

        name_map = {}
        try:
            name_map = _load_auto_universe_name_map()
        except Exception:
            name_map = {}

        if name_map:
            for t, n in name_map.items():
                if _match(n):
                    out.append(str(t).upper())
                    if len(out) >= max_hits:
                        break

        if len(out) < max_hits:
            for t, v in MARKET_INSIGHTS.items():
                if _match(v.get("name") or ""):
                    out.append(str(t).upper())
                    if len(out) >= max_hits:
                        break

        out = sorted({_normalize_kl_ticker(x) for x in out if _normalize_kl_ticker(x)})
        return out
    except Exception:
        return sorted({_normalize_kl_ticker(x) for x in out if _normalize_kl_ticker(x)})


def _top100_membership_set(max_age_days: int = 30) -> set[str]:
    try:
        fbm100, _ = refresh_index_components("fbm100", force=False, max_age_days=max_age_days, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        fbm100 = [str(x).upper().strip() for x in (fbm100 or []) if x]
        if len(fbm100) >= 70:
            return set(fbm100)
    except Exception:
        pass

    s = set()
    try:
        s |= set(refresh_klci_components(force=False, max_age_days=max_age_days)[0] or [])
    except Exception:
        s |= set(list(KLCI_COMPONENTS))
    try:
        fbm70, _ = refresh_index_components("fbm70", force=False, max_age_days=max_age_days, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        if fbm70:
            s |= set(fbm70)
    except Exception:
        pass
    if s:
        out = {str(x).upper().strip() for x in s if x}
        if len(out) >= 40:
            return out

    try:
        curated = set(STOCK_DISCOVERY_UNIVERSE)
        curated = {str(x).upper().strip() for x in curated if x}
        if curated:
            return curated
    except Exception:
        pass

    return {str(x).upper().strip() for x in list(KLCI_COMPONENTS)}


def _filter_to_large_mid(tickers: list[str]) -> list[str]:
    u = [str(x).upper().strip() for x in (tickers or []) if _normalize_kl_ticker(x)]
    u = [x for x in u if x]
    membership = set()
    try:
        membership |= _top100_membership_set(max_age_days=30)
    except Exception:
        membership |= {str(x).upper().strip() for x in list(KLCI_COMPONENTS)}
    try:
        membership |= {str(x).upper().strip() for x in MARKET_INSIGHTS.keys()}
    except Exception:
        pass
    if not membership:
        return sorted(set(u))
    return sorted({t for t in u if t in membership})


def get_sector_large_cap_universe(mode: str) -> tuple[list[str], str]:
    m = str(mode or "").lower().strip()
    pinned = {
        "sector-tech": [
            "0097.KL",
            "0128.KL",
            "0166.KL",
            "0208.KL",
            "3867.KL",
            "4456.KL",
            "5005.KL",
            "5286.KL",
            "5292.KL",
            "7204.KL",
            "7471.KL",
            "9334.KL",
        ],
        "sector-utilities": ["5347.KL", "6742.KL", "4677.KL", "5209.KL", "5264.KL"],
        "sector-infra": ["5398.KL", "3336.KL", "7277.KL", "3816.KL", "5246.KL"],
        "sector-property": ["5227.KL", "5212.KL", "5211.KL", "5176.KL", "5288.KL", "5263.KL", "5148.KL"],
        "sector-consumer": ["4707.KL", "2836.KL", "3255.KL", "3689.KL", "7084.KL", "5296.KL", "4065.KL"],
        "sector-banks": ["1155.KL", "1023.KL", "1295.KL", "1066.KL", "5819.KL", "2488.KL", "5258.KL", "5185.KL"],
        "sector-healthcare": ["5225.KL", "5878.KL", "5168.KL", "7113.KL", "7153.KL", "7106.KL"],
        "sector-energy": ["5681.KL", "6033.KL", "5183.KL", "5210.KL", "5141.KL", "5199.KL"],
        "sector-plantation": ["5285.KL", "2445.KL", "1961.KL", "2291.KL", "2089.KL", "5012.KL"],
        "sector-telco": ["4863.KL", "6012.KL", "5031.KL", "6399.KL", "6888.KL"],
        "sector-industrial": ["8869.KL", "4731.KL", "3794.KL", "9822.KL", "8125.KL"],
    }
    presets = {
        "sector-tech": [
            "INARI",
            "VITROX",
            "MALAYSIAN PACIFIC",
            "UNISEM",
            "GREATECH",
            "D&O",
            "D&O GREEN",
            "DNEX",
            "FRONTKEN",
            "UWC",
            "MI TECHNOVATION",
            "KOBAY",
        ],
        "sector-utilities": ["YTL", "YTL POWER", "TENAGA", "MALAKOFF", "RANHILL", "GAS MALAYSIA"],
        "sector-infra": ["IJM", "GAMUDA", "DIALOG", "MISC", "WESTPORTS"],
        "sector-property": ["IGB REIT", "PAVILION REIT", "SUNWAY", "SUNWAY REIT", "IOI PROPERTIES", "SIME DARBY PROPERTY", "UEM SUNRISE", "SP SETIA"],
        "sector-consumer": ["HEINEKEN", "CARLSBERG", "NESTLE", "QL", "MR DIY", "PPB", "FRASER"],
        "sector-banks": ["MAYBANK", "MALAYAN BANKING", "CIMB", "PUBLIC BANK", "RHB", "HONG LEONG BANK", "AMMB", "AFFIN", "BANK ISLAM"],
        "sector-healthcare": ["IHH", "KPJ", "PHARMANIAGA", "DUOPHARMA", "HARTALEGA", "TOP GLOVE", "KOSSAN", "SUPERMAX"],
        "sector-energy": ["PETDAG", "PETRONAS DAGANGAN", "PETGAS", "PETRONAS GAS", "PCHEM", "PETRONAS CHEMICALS", "ARMADA", "DAYANG", "HIBISCUS"],
        "sector-plantation": ["SIME DARBY PLANTATION", "FGV", "IOI CORP", "KLK", "GENTING PLANTATION", "UNITED PLANTATIONS", "TA ANN"],
        "sector-telco": ["TELEKOM MALAYSIA", "MAXIS", "CELCOMDIGI", "TIME DOTCOM", "ASTRO"],
        "sector-industrial": ["PRESS METAL", "SCIENTEX", "SAM ENGINEERING", "MALAYAN CEMENT", "LCTITAN"],
    }
    if m not in presets:
        return [], "unknown"
    u = _find_tickers_by_name_keywords(presets[m], max_hits=250)

    keep = set(_filter_to_large_mid(u))
    for t in pinned.get(m, []):
        nt = _normalize_kl_ticker(t)
        if nt:
            keep.add(nt)
    u = sorted(keep)
    return u, m


def _fetch_klci_from_yahoo() -> list[str]:
    try:
        url = "https://finance.yahoo.com/quote/%5EKLSE/components"
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=25,
        )
        if r.status_code != 200:
            return []
        tickers = _extract_kl_codes_from_text(r.text)
        if 25 <= len(tickers) <= 40:
            return tickers
        return []
    except Exception:
        return []


def _fetch_klci_from_wikipedia() -> list[str]:
    try:
        from bs4 import BeautifulSoup

        url = "https://en.wikipedia.org/wiki/FTSE_Bursa_Malaysia_KLCI"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        anchor = soup.find(id="Constituents")
        if not anchor:
            return []
        table = anchor.find_parent().find_next("table", class_="wikitable")
        if not table:
            return []
        header_row = table.find("tr")
        headers = [th.get_text(" ", strip=True).lower() for th in header_row.find_all("th")] if header_row else []
        code_idx = None
        for i, h in enumerate(headers):
            if "code" in h or "stock code" in h or "ticker" in h or "symbol" in h:
                code_idx = i
                break
        if code_idx is None:
            return []

        out = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if not cells or len(cells) <= code_idx:
                continue
            cell_text = cells[code_idx].get_text(" ", strip=True)
            m = re.search(r"\b(\d{4})\b", str(cell_text))
            if not m:
                continue
            out.append(f"{m.group(1)}.KL")

        out = sorted(set(out))
        if 25 <= len(out) <= 40:
            return out
        return []
    except Exception:
        return []


def refresh_klci_components(force: bool = False, max_age_days: int = 30) -> tuple[list[str], str]:
    try:
        if not force and os.path.exists(KLCI_COMPONENTS_AUTO_FILE):
            try:
                age_s = (pd.Timestamp.now() - pd.Timestamp.fromtimestamp(os.path.getmtime(KLCI_COMPONENTS_AUTO_FILE))).total_seconds()
                if age_s < float(max_age_days) * 86400.0:
                    cached = [_normalize_kl_ticker(x) for x in _read_text_lines(KLCI_COMPONENTS_AUTO_FILE)]
                    cached = [x for x in cached if x]
                    if 25 <= len(cached) <= 40:
                        return cached, "cache"
            except Exception:
                pass

        for src, fn in [("yahoo", _fetch_klci_from_yahoo), ("wikipedia", _fetch_klci_from_wikipedia)]:
            u = fn() or []
            u = [_normalize_kl_ticker(x) for x in u]
            u = [x for x in u if x]
            u = sorted(set(u))
            if 25 <= len(u) <= 40:
                _write_text_lines(KLCI_COMPONENTS_AUTO_FILE, [t.replace(".KL", "") for t in u])
                return u, src

        return list(KLCI_COMPONENTS), "static"
    except Exception:
        return list(KLCI_COMPONENTS), "static"


def get_klci_components_info(max_age_days: int = 30) -> dict:
    try:
        tickers, src = refresh_klci_components(force=False, max_age_days=max_age_days)
        updated = None
        if os.path.exists(KLCI_COMPONENTS_AUTO_FILE):
            try:
                updated = pd.Timestamp.fromtimestamp(os.path.getmtime(KLCI_COMPONENTS_AUTO_FILE)).isoformat()
            except Exception:
                updated = None
        return {"tickers": tickers, "source": src, "updated_at": updated}
    except Exception:
        return {"tickers": list(KLCI_COMPONENTS), "source": "static", "updated_at": None}

STOCK_DISCOVERY_UNIVERSE = sorted(
    set(
        KLCI_COMPONENTS
        + [
            k
            for k in MARKET_INSIGHTS.keys()
            if isinstance(k, str) and k.upper().endswith(".KL")
        ]
    )
)

BURSA_UNIVERSE_FILE = os.path.join(os.path.dirname(__file__), "bursa_universe.csv")
BURSA_UNIVERSE_AUTO_FILE = os.path.join(os.path.dirname(__file__), "bursa_universe_auto.csv")

_AUTO_UNIVERSE_NAME_CACHE = {"mtime": None, "map": {}}
_AUTO_UNIVERSE_NAME_NORM_CACHE = {"mtime": None, "tokens": {}}


def _read_universe_codes(raw_codes):
    out = []
    for x in raw_codes or []:
        s = str(x).strip().upper()
        if not s:
            continue
        s = s.replace(" ", "")
        base = s
        if base.endswith(".KL"):
            base = base[:-3]

        if base.startswith("^") or base.endswith("=F"):
            continue
        if "REIT" in base or "ETF" in base:
            continue
        if base.endswith("EA"):
            continue
        if base.endswith(("WA", "WB", "WC", "WD", "WE", "WF", "WG")) or "-W" in base:
            continue

        if base.isdigit() and len(base) == 4:
            out.append(f"{base}.KL")
    return sorted(set(out))


def _load_auto_universe_name_map():
    try:
        if not os.path.exists(BURSA_UNIVERSE_AUTO_FILE):
            return {}
        mtime = os.path.getmtime(BURSA_UNIVERSE_AUTO_FILE)
        if _AUTO_UNIVERSE_NAME_CACHE.get("mtime") == mtime and _AUTO_UNIVERSE_NAME_CACHE.get("map"):
            return _AUTO_UNIVERSE_NAME_CACHE["map"]

        try:
            df = pd.read_csv(BURSA_UNIVERSE_AUTO_FILE, dtype=str)
            cols = {str(c).strip().lower(): c for c in df.columns}
            code_col = cols.get("ticker") or cols.get("symbol") or cols.get("code")
            name_col = cols.get("name")
            if not code_col or not name_col:
                _AUTO_UNIVERSE_NAME_CACHE["mtime"] = mtime
                _AUTO_UNIVERSE_NAME_CACHE["map"] = {}
                return {}
            out = {}
            for _, row in df[[code_col, name_col]].iterrows():
                code = str(row[code_col]).strip().upper()
                name = str(row[name_col]).strip()
                if not code or not name:
                    continue
                if code.isdigit() and len(code) == 4:
                    out[f"{code}.KL"] = name
                elif code.endswith(".KL"):
                    out[code] = name
            _AUTO_UNIVERSE_NAME_CACHE["mtime"] = mtime
            _AUTO_UNIVERSE_NAME_CACHE["map"] = out
            try:
                _AUTO_UNIVERSE_NAME_NORM_CACHE["mtime"] = mtime
                _AUTO_UNIVERSE_NAME_NORM_CACHE["tokens"] = {}
            except Exception:
                pass
            return out
        except Exception:
            _AUTO_UNIVERSE_NAME_CACHE["mtime"] = mtime
            _AUTO_UNIVERSE_NAME_CACHE["map"] = {}
            return {}
    except Exception:
        return {}


def _auto_universe_name(ticker: str):
    try:
        t = str(ticker).upper().strip()
        if not t:
            return None
        return _load_auto_universe_name_map().get(t)
    except Exception:
        return None


def _name_tokens(s: str) -> set[str]:
    try:
        x = str(s or "").upper()
        x = x.replace("&", " AND ")
        x = re.sub(r"[^A-Z0-9 ]+", " ", x)
        x = re.sub(r"\s+", " ", x).strip()
        if not x:
            return set()
        drop = {
            "BERHAD",
            "BHD",
            "BHDS",
            "GROUP",
            "HOLDINGS",
            "HOLDING",
            "MALAYSIA",
            "INTERNATIONAL",
            "CORPORATION",
            "CORP",
            "COMPANY",
            "CO",
            "PUBLIC",
            "LIMITED",
            "LTD",
            "SDN",
            "BHD",
            "THE",
        }
        toks = [t for t in x.split(" ") if t and t not in drop]
        return set(toks)
    except Exception:
        return set()


def _best_ticker_match_by_name(company_name: str) -> str | None:
    try:
        target = _name_tokens(company_name)
        if len(target) < 2:
            return None
        name_map = _load_auto_universe_name_map()
        if not name_map:
            return None

        mtime = None
        try:
            mtime = os.path.getmtime(BURSA_UNIVERSE_AUTO_FILE)
        except Exception:
            mtime = None

        if _AUTO_UNIVERSE_NAME_NORM_CACHE.get("mtime") != mtime or not _AUTO_UNIVERSE_NAME_NORM_CACHE.get("tokens"):
            tok_map = {}
            for t, n in name_map.items():
                tok_map[t] = _name_tokens(n)
            _AUTO_UNIVERSE_NAME_NORM_CACHE["mtime"] = mtime
            _AUTO_UNIVERSE_NAME_NORM_CACHE["tokens"] = tok_map

        tok_map = _AUTO_UNIVERSE_NAME_NORM_CACHE.get("tokens") or {}
        best_t = None
        best_score = 0.0
        for t, toks in tok_map.items():
            if not toks:
                continue
            inter = len(target & toks)
            if inter == 0:
                continue
            score = inter / float(max(len(target), len(toks)))
            if score > best_score:
                best_score = score
                best_t = t
        if best_t and best_score >= 0.5:
            return str(best_t).upper().strip()
        return None
    except Exception:
        return None


def _fetch_universe_from_github():
    url = "https://raw.githubusercontent.com/KennethChua1998/BursaMalaysiaWebScrapper/master/stock_list.csv"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        r.raise_for_status()
        text = r.text
        if not text:
            return [], {}
        reader = csv.DictReader(text.splitlines())
        raw_codes = []
        name_map = {}
        for row in reader:
            code = str(row.get("code") or "").strip()
            name = str(row.get("name") or "").strip()
            if not code:
                continue
            raw_codes.append(code)
            if name and code.isdigit() and len(code) == 4:
                name_map[f"{code}.KL"] = name
        tickers = _read_universe_codes(raw_codes)
        return tickers, name_map
    except Exception:
        return [], {}


def _load_or_refresh_auto_universe(max_age_days: int = 14):
    try:
        if os.path.exists(BURSA_UNIVERSE_AUTO_FILE):
            try:
                age_s = (pd.Timestamp.now() - pd.Timestamp.fromtimestamp(os.path.getmtime(BURSA_UNIVERSE_AUTO_FILE))).total_seconds()
                if age_s < float(max_age_days) * 86400.0:
                    try:
                        with open(BURSA_UNIVERSE_AUTO_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            header = str(f.readline() or "").strip().lower()
                        if "name" in header and ("code" in header or "ticker" in header or "symbol" in header):
                            return _load_universe_from_file(BURSA_UNIVERSE_AUTO_FILE)
                    except Exception:
                        return _load_universe_from_file(BURSA_UNIVERSE_AUTO_FILE)
            except Exception:
                pass

        u, name_map = _fetch_universe_from_github()
        if u:
            try:
                with open(BURSA_UNIVERSE_AUTO_FILE, "w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["code", "name"])
                    for t in u:
                        w.writerow([t.replace(".KL", ""), name_map.get(t) or ""])
            except Exception:
                pass
            try:
                _AUTO_UNIVERSE_NAME_CACHE["mtime"] = os.path.getmtime(BURSA_UNIVERSE_AUTO_FILE)
                _AUTO_UNIVERSE_NAME_CACHE["map"] = name_map
            except Exception:
                pass
            return u
        return _load_universe_from_file(BURSA_UNIVERSE_FILE)
    except Exception:
        return []

def _load_universe_from_file(path: str):
    try:
        if not path or not os.path.exists(path):
            return []
        try:
            df = pd.read_csv(path, dtype=str)
            cols = [c for c in df.columns if str(c).strip().lower() in {"ticker", "symbol", "code"}]
            if cols:
                raw = df[cols[0]].dropna().astype(str).tolist()
            else:
                raw = df.iloc[:, 0].dropna().astype(str).tolist()
        except Exception:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = [line.strip() for line in f.readlines()]
        cleaned = []
        for x in raw:
            s = str(x).strip().upper()
            if not s:
                continue
            if s in {"TICKER", "SYMBOL", "CODE"}:
                continue
            cleaned.append(s)
        return _read_universe_codes(cleaned)
    except Exception:
        return []

def get_stock_universe(mode: str = "curated"):
    m = str(mode or "").lower().strip()
    if m in {"focus", "focus-sectors", "myfocus", "focus_large_mid"}:
        parts = []
        for k in ["sector-tech", "sector-energy", "sector-banks", "sector-utilities", "sector-infra", "sector-telco"]:
            u, _ = get_sector_large_cap_universe(k)
            parts.extend(u)

        ai_pinned = [
            "0097.KL",
            "0128.KL",
            "0166.KL",
            "0208.KL",
            "3867.KL",
            "4456.KL",
            "5005.KL",
            "5286.KL",
            "5292.KL",
            "7204.KL",
            "7471.KL",
            "9334.KL",
            "4677.KL",
            "6742.KL",
            "4863.KL",
            "5031.KL",
            "6947.KL",
        ]
        parts.extend([t for t in (_normalize_kl_ticker(x) for x in ai_pinned) if t])

        parts = _filter_to_large_mid(parts)
        parts = sorted({str(x).upper().strip() for x in parts if _normalize_kl_ticker(x)})
        return parts, "focus"
    if m.startswith("sector-"):
        u, src = get_sector_large_cap_universe(m)
        return u, src
    if m in {"klci", "big", "bigcap", "large", "largecap"}:
        if KLCI_AUTO_UPDATE_ENABLED:
            u, src = refresh_klci_components(force=bool(INDEX_FORCE_REFRESH), max_age_days=30)
            return u, f"klci-{src}"
        return list(KLCI_COMPONENTS), "klci-static"
    if m in {"fbm70", "mid70", "m70"}:
        u, src = refresh_index_components("fbm70", force=bool(INDEX_FORCE_REFRESH), max_age_days=30, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        if u:
            return u, f"fbm70-{src}"
        return [], "fbm70-unavailable"
    if m in {"fbm100", "top100", "t100", "top_100"}:
        u, src = refresh_index_components("fbm100", force=bool(INDEX_FORCE_REFRESH), max_age_days=30, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        if u:
            return u, f"fbm100-{src}"
        return [], "fbm100-unavailable"
    if m in {"smallcap", "small", "sc"}:
        u, src = refresh_index_components("smallcap", force=bool(INDEX_FORCE_REFRESH), max_age_days=30, allow_network=bool(INDEX_AUTO_UPDATE_ENABLED))
        if u:
            return u, f"smallcap-{src}"
        return [], "smallcap-unavailable"
    if m in {"auto", "malaysia", "my"}:
        u = _load_or_refresh_auto_universe()
        if u:
            return u, "auto"
    if m in {"file", "full", "all"}:
        u = _load_universe_from_file(BURSA_UNIVERSE_FILE)
        if u:
            return u, "file"
    return STOCK_DISCOVERY_UNIVERSE, "curated"

# --- MALAYSIAN FUTURES ---
FUTURES_COMPONENTS = [
    "FKLI=F", # FTSE Bursa Malaysia KLCI Futures
    "FCPO=F", # Crude Palm Oil Futures
    "FM70=F"  # FTSE Bursa Malaysia Mid 70 Index Futures
]

def get_futures_breakouts():
    """
    Specifically analyzes Malaysian Futures for breakouts.
    """
    results = []
    # Fetching individually for futures as they often have specific symbol issues
    for ticker in FUTURES_COMPONENTS:
        # Try a longer period for futures indices
        df, name = get_stock_data(ticker, period="2y")
        
        if df is None or df.empty:
            continue

        if len(df) >= 2:
            try:
                last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
                last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
                if (pd.isna(last_close) or pd.isna(last_open)):
                    df = df.iloc[:-1]
                elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0 and not _is_today_kl(df.index[-1]):
                    df = df.iloc[:-1]
            except Exception:
                pass

        try:
            last_close = float(df["Close"].iloc[-1])
            if not (last_close > 0.0):
                continue
        except Exception:
            continue

        # Be slightly more lenient with row count for futures
        # If it's a major index with very short history (like FBM70.FGI),
        # we provide a fallback row count.
        min_r = 30 if len(df) >= 30 else len(df)
        analysis = analyze_breakout(ticker, df, name, min_rows=min_r)
        if analysis:
            results.append(analysis)
    return results

def get_top_breakouts(limit=10, model="v2", universe_mode="curated", universe=None, sector_allowlist=None, signal_lookback=5, max_runup_pct=None, max_pullback_pct=None, retest_days=0, max_tickers=None):
    """
    Scans a stock universe and returns the top N stocks 
    based on their breakout scores.
    """
    all_results = []
    benchmark_df = None
    m = str(model).lower()
    if m == "v2":
        try:
            bench = yf.Ticker("^KLSE")
            benchmark_df = bench.history(period="1y")
            if benchmark_df is not None and not benchmark_df.empty:
                benchmark_df = benchmark_df.dropna(subset=[c for c in ["Close"] if c in benchmark_df.columns])
        except Exception:
            benchmark_df = None
    
    tickers = universe if universe is not None else get_stock_universe(universe_mode)[0]
    try:
        if m == "v3i" and max_tickers is None:
            max_tickers = 50

        if max_tickers is not None:
            n = int(max_tickers)
            if n > 0:
                tickers = tickers[:n]
    except Exception:
        pass
    allow = None
    if m in {"v3", "v3i"} and sector_allowlist:
        allow = {str(x).strip().lower() for x in sector_allowlist if str(x).strip()}

    if m == "v3i":
        token = _get_itick_token()
        if not token:
            return []

        def _chunks(seq, size: int):
            out = []
            buf = []
            for x in seq:
                buf.append(x)
                if len(buf) >= size:
                    out.append(buf)
                    buf = []
            if buf:
                out.append(buf)
            return out

        for batch in _chunks(list(tickers), 10):
            daily_map: dict[str, tuple[pd.DataFrame, str]] = {}
            codes = []
            for ticker in batch:
                if allow:
                    t = str(ticker).upper().strip()
                    code = t.split(".")[0]
                    insight = MARKET_INSIGHTS.get(t)
                    if not insight:
                        for _, v in MARKET_INSIGHTS.items():
                            if v.get("code") == code:
                                insight = v
                                break
                    sector = insight.get("sector") if insight else None
                    if sector and str(sector).strip().lower() not in allow:
                        continue

                df, resolved_name = get_stock_data(ticker, period="1y")
                if df is None or df.empty:
                    continue
                t = str(ticker).upper().strip()
                code = t.split(".")[0]
                daily_map[code] = (df, resolved_name)
                codes.append(code)

            if not codes:
                continue

            intramap = _itick_stock_klines(codes, ktype=2, limit=160, region=None)
            for code, (dfd, resolved_name) in daily_map.items():
                intra = intramap.get(code)
                if intra is None or intra.empty:
                    continue
                ticker_full = f"{code}.KL" if (code.isdigit() and len(code) == 4) else code
                analysis = analyze_breakout_v3_intraday(
                    ticker_full,
                    dfd,
                    intra,
                    resolved_name=resolved_name,
                    max_runup_pct=max_runup_pct,
                    min_intraday_bars=40,
                )
                if analysis:
                    all_results.append(analysis)

        all_results.sort(
            key=lambda x: (
                bool(x.get("breakout_candle_valid")),
                int(x.get("score", 0)),
                -float(x.get("runup_pct", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return all_results[:limit]
    # Using individual fetching for better error handling in this environment
    for ticker in tickers:
        if allow:
            t = str(ticker).upper().strip()
            code = t.split(".")[0]
            insight = MARKET_INSIGHTS.get(t)
            if not insight:
                for _, v in MARKET_INSIGHTS.items():
                    if v.get("code") == code:
                        insight = v
                        break
            sector = None
            if insight:
                sector = insight.get("sector")
            if sector and str(sector).strip().lower() not in allow:
                continue
        df, resolved_name = get_stock_data(ticker, period="1y")
        if df is None or df.empty:
            continue

        if len(df) >= 2:
            try:
                last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
                last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
                if (pd.isna(last_close) or pd.isna(last_open)):
                    df = df.iloc[:-1]
                elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0 and not _is_today_kl(df.index[-1]):
                    df = df.iloc[:-1]
            except Exception:
                pass

        try:
            last_close = float(df["Close"].iloc[-1])
            if not (last_close > 0.0):
                continue
        except Exception:
            continue

        try:
            if "Volume" in df.columns:
                tail_vol = pd.to_numeric(df["Volume"].tail(5), errors="coerce")
                if tail_vol.fillna(0).max() <= 0:
                    continue
        except Exception:
            continue

        if m == "v3":
            analysis = analyze_breakout_v3(ticker, df, resolved_name, benchmark_df=benchmark_df, min_rows=120, signal_lookback=signal_lookback, max_runup_pct=max_runup_pct, max_pullback_pct=max_pullback_pct, retest_days=retest_days)
        elif m == "v2":
            analysis = analyze_breakout_v2(ticker, df, resolved_name, benchmark_df=benchmark_df, min_rows=120)
        else:
            analysis = analyze_breakout(ticker, df, resolved_name)
        if analysis:
            all_results.append(analysis)
    
    if str(model).lower() == "v3":
        all_results.sort(
            key=lambda x: (
                bool(x.get("retest_confirmed")),
                bool(x.get("breakout_candle_valid")),
                int(x.get("score", 0)),
                -float(x.get("rsi", 0.0) or 0.0),
            ),
            reverse=True,
        )
    else:
        all_results.sort(key=lambda x: (x['score'], -x['rsi']), reverse=True)
    
    return all_results[:limit]

def search_bursa(query):
    """
    Searches for a Bursa Malaysia stock code or symbol.
    """
    query_upper = str(query or "").upper().strip()
    if not query_upper:
        return None
    
    # Precise mapping for futures
    if query_upper == "FKLI": return "FKLI=F"
    if query_upper == "FCPO": return "FCPO=F"
    if query_upper == "FM70": return "FM70=F"
    
    if query_upper in MARKET_INSIGHTS:
        return query_upper

    if query_upper.endswith(".KL") and len(query_upper.split(".")[0]) == 4 and query_upper.split(".")[0].isdigit():
        return query_upper

    if query_upper in {"^KLSE", "^KLSI"}:
        return "^KLSE"

    if query_upper.isdigit() and len(query_upper) == 4:
        return f"{query_upper}.KL"

    try:
        for k, v in MARKET_INSIGHTS.items():
            code = str(v.get("code") or "").strip().upper()
            name = str(v.get("name") or "").strip().upper()
            if query_upper == name or query_upper == code:
                return str(k).upper().strip()
    except Exception:
        pass

    try:
        name_map = _load_auto_universe_name_map()
        if name_map:
            for t, n in name_map.items():
                if query_upper == str(n).strip().upper():
                    return str(t).upper().strip()
            for t, n in name_map.items():
                if query_upper in str(n).strip().upper():
                    return str(t).upper().strip()
    except Exception:
        pass

    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, params={"q": query_upper, "quotesCount": 10}, timeout=15).json()
        for quote in response.get('quotes', []):
            if quote.get('symbol', '').endswith('.KL'):
                return quote['symbol']
    except Exception:
        pass
    return None
