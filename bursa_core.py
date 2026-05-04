import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import datetime
import requests
import re

# Disable yfinance cache to avoid database errors
try:
    import yfinance as yf
    import os
    
    # On Streamlit Cloud or Linux, use /tmp for cache if current dir is not writable
    cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
    
    # Check if we are on Streamlit Cloud
    if os.environ.get('STREAMLIT_SERVER_PORT') or not os.access(os.getcwd(), os.W_OK):
        cache_path = "/tmp/.yfinance_cache"
        
    if not os.path.exists(cache_path):
        try:
            os.makedirs(cache_path, exist_ok=True)
        except:
            pass
    
    # CRITICAL: Completely disable cache if it causes issues, or set to writable path
    try:
        yf.set_tz_cache_location(cache_path)
    except Exception:
        try:
            # Fallback: Disable cache entirely to avoid peewee errors
            import yfinance.cache as yf_cache
            yf_cache._db.close()
        except:
            pass
    
    os.environ['YFINANCE_CACHE_DIR'] = cache_path
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

    if ticker == "FKLI=F":
        df = None
        try:
            stock = yf.Ticker("^KLSE")
            df = stock.history(period=period)
            if df.empty and period != "1mo":
                df = stock.history(period="1mo")
        except Exception:
            df = None

        price = _tradingview_last_price_myr("MYX-FKLI1!")
        if df is not None and not df.empty:
            if price is not None:
                try:
                    df = df.copy()
                    df.iloc[-1, df.columns.get_loc("Close")] = price
                    for c in ["Open", "High", "Low"]:
                        if c in df.columns and pd.isna(df[c].iloc[-1]):
                            df.iloc[-1, df.columns.get_loc(c)] = price
                except Exception:
                    pass
            return df, MARKET_INSIGHTS.get("FKLI=F", {}).get("name", "KLCI FUTURES")
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
                    if len(df) >= 1 and all(c in df.columns for c in ["Open", "High", "Low", "Close", "Volume"]):
                        last = df.iloc[-1]
                        if (pd.isna(last["Open"]) or pd.isna(last["High"]) or pd.isna(last["Low"]) or pd.isna(last["Close"])) and float(last["Volume"]) > 0.0:
                            intra = None
                            for interval in ["5m", "15m", "30m", "60m"]:
                                try:
                                    intra = stock.history(period="1d", interval=interval)
                                    if intra is not None and not intra.empty:
                                        break
                                except Exception:
                                    intra = None
                            if intra is not None and not intra.empty and all(c in intra.columns for c in ["Open", "High", "Low", "Close", "Volume"]):
                                o = float(intra["Open"].iloc[0])
                                h = float(pd.to_numeric(intra["High"], errors="coerce").max())
                                l = float(pd.to_numeric(intra["Low"], errors="coerce").min())
                                c = float(intra["Close"].iloc[-1])
                                v = float(pd.to_numeric(intra["Volume"], errors="coerce").fillna(0).sum())
                                if all(x == x for x in [o, h, l, c]) and v >= 0:
                                    df = df.copy()
                                    df.iloc[-1, df.columns.get_loc("Open")] = o
                                    df.iloc[-1, df.columns.get_loc("High")] = h
                                    df.iloc[-1, df.columns.get_loc("Low")] = l
                                    df.iloc[-1, df.columns.get_loc("Close")] = c
                                    df.iloc[-1, df.columns.get_loc("Volume")] = v
                except Exception:
                    pass

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
            elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0:
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
    
    # --- NAME RESOLUTION LOGIC ---
    name = None
    code = ticker.split(".")[0]
    analysis = "Technical breakout analysis based on live data."
    catalyst = "Market momentum / Trend following."

    # 1. Try exact match in MARKET_INSIGHTS
    insight = MARKET_INSIGHTS.get(ticker)
    
    # 2. Try match by code if ticker match fails (e.g. 6888 vs 6888.KL)
    if not insight:
        for k, v in MARKET_INSIGHTS.items():
            if v.get('code') == code:
                insight = v
                break
    
    if insight:
        name = insight["name"]
        code = insight["code"]
        analysis = insight["analysis"]
        catalyst = insight["catalyst"]
    else:
        # 3. Fallback to resolved_name or ticker cleaning
        name = resolved_name or code
        
    # Final cleanup: If name is still just the ticker code, try to clean it
    if name == ticker or name == code or ".KL" in str(name):
        name = str(name).replace(".KL", "").strip()
    
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

# --- KLCI COMPONENTS (Top 30 Stocks) ---
KLCI_COMPONENTS = [
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5183.KL", 
    "5225.KL", "6947.KL", "6888.KL", "6012.KL", "5819.KL",
    "8869.KL", "6033.KL", "3816.KL", "1066.KL", "4707.KL",
    "1961.KL", "2445.KL", "4065.KL", "3182.KL", "4715.KL",
    "7277.KL", "4197.KL", "5285.KL", "5681.KL", "1015.KL",
    "1082.KL", "0166.KL", "5296.KL", "5246.KL", "4677.KL"
]

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
                elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0:
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

def get_top_breakouts(limit=10):
    """
    Scans the KLCI components and returns the top N stocks 
    based on their breakout scores.
    """
    all_results = []
    
    # Using individual fetching for better error handling in this environment
    for ticker in KLCI_COMPONENTS:
        df, resolved_name = get_stock_data(ticker, period="1y")
        if df is None or df.empty:
            continue

        if len(df) >= 2:
            try:
                last_close = df["Close"].iloc[-1] if "Close" in df.columns else None
                last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
                if (pd.isna(last_close) or pd.isna(last_open)):
                    df = df.iloc[:-1]
                elif "Volume" in df.columns and float(df["Volume"].iloc[-1]) == 0.0 and float(df["Volume"].iloc[-2]) > 0.0:
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

        analysis = analyze_breakout(ticker, df, resolved_name)
        if analysis:
            all_results.append(analysis)
    
    # Sort by score descending, then by RSI (lower RSI preferred if scores equal)
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
