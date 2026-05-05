import os
import pandas as pd
import datetime
import requests
import re

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
                if name == ticker or ".KL" in str(name):
                    try:
                        yf_info = stock.info
                        name = yf_info.get('shortName') or yf_info.get('longName') or name
                    except:
                        pass
                return df, name
        except Exception:
            continue
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

    if name == t or name == code or ".KL" in str(name):
        name = str(name).replace(".KL", "").strip()

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

    if name == t or name == code or ".KL" in str(name):
        name = str(name).replace(".KL", "").strip()

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

# --- KLCI COMPONENTS (Top 30 Stocks) ---
KLCI_COMPONENTS = [
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5183.KL", 
    "5225.KL", "6947.KL", "6888.KL", "6012.KL", "5819.KL",
    "8869.KL", "6033.KL", "3816.KL", "1066.KL", "4707.KL",
    "1961.KL", "2445.KL", "4065.KL", "3182.KL", "4715.KL",
    "7277.KL", "4197.KL", "5285.KL", "5681.KL", "1015.KL",
    "1082.KL", "0166.KL", "5296.KL", "5246.KL", "4677.KL"
]

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


def _fetch_universe_from_github():
    url = "https://raw.githubusercontent.com/KennethChua1998/BursaMalaysiaWebScrapper/master/stock_list.csv"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        r.raise_for_status()
        lines = r.text.splitlines()
        if not lines:
            return []
        raw = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if not parts:
                continue
            raw.append(parts[0])
        return _read_universe_codes(raw)
    except Exception:
        return []


def _load_or_refresh_auto_universe(max_age_days: int = 14):
    try:
        if os.path.exists(BURSA_UNIVERSE_AUTO_FILE):
            try:
                age_s = (pd.Timestamp.now() - pd.Timestamp.fromtimestamp(os.path.getmtime(BURSA_UNIVERSE_AUTO_FILE))).total_seconds()
                if age_s < float(max_age_days) * 86400.0:
                    return _load_universe_from_file(BURSA_UNIVERSE_AUTO_FILE)
            except Exception:
                pass

        u = _fetch_universe_from_github()
        if u:
            try:
                with open(BURSA_UNIVERSE_AUTO_FILE, "w", encoding="utf-8") as f:
                    for t in u:
                        f.write(f"{t}\n")
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
    if str(model).lower() == "v2":
        try:
            bench = yf.Ticker("^KLSE")
            benchmark_df = bench.history(period="1y")
            if benchmark_df is not None and not benchmark_df.empty:
                benchmark_df = benchmark_df.dropna(subset=[c for c in ["Close"] if c in benchmark_df.columns])
        except Exception:
            benchmark_df = None
    
    tickers = universe if universe is not None else get_stock_universe(universe_mode)[0]
    try:
        if max_tickers is not None:
            n = int(max_tickers)
            if n > 0:
                tickers = tickers[:n]
    except Exception:
        pass
    allow = None
    if str(model).lower() == "v3" and sector_allowlist:
        allow = {str(x).strip().lower() for x in sector_allowlist if str(x).strip()}
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

        m = str(model).lower()
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
    query_upper = query.upper().strip()
    
    # Precise mapping for futures
    if query_upper == "FKLI": return "FKLI=F"
    if query_upper == "FCPO": return "FCPO=F"
    if query_upper == "FM70": return "FM70=F"
    
    if query.isdigit() and len(query) == 4:
        return f"{query}.KL"
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=5"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers).json()
        for quote in response.get('quotes', []):
            if quote.get('symbol', '').endswith('.KL'):
                return quote['symbol']
    except Exception:
        pass
    return None
