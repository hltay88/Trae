import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import datetime
import requests

# Disable yfinance cache to avoid database errors
try:
    import yfinance as yf
    import os
    
    # On Streamlit Cloud or Linux, use /tmp for cache if current dir is not writable
    cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
    
    # Check if we are on Streamlit Cloud (usually has 'STREAMLIT_RUNTIME_ENV' or similar)
    if os.environ.get('STREAMLIT_SERVER_PORT') or not os.access(os.getcwd(), os.W_OK):
        cache_path = "/tmp/.yfinance_cache"
        
    if not os.path.exists(cache_path):
        try:
            os.makedirs(cache_path, exist_ok=True)
        except:
            pass
    
    # Try to set cache location
    try:
        yf.set_tz_cache_location(cache_path)
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
    "FKLI=F": {"code": "FKLI", "name": "KLCI FUTURES", "sector": "Futures", "analysis": "Proxy for the underlying FBM KLCI index.", "catalyst": "Market sentiment."},
    "FCPO=F": {"code": "FCPO", "name": "CPO FUTURES", "sector": "Futures", "analysis": "Global benchmark for Crude Palm Oil.", "catalyst": "Supply/demand in edible oils."},
    "FM70=F": {"code": "FM70", "name": "MID 70 FUTURES", "sector": "Futures", "analysis": "Proxy for the FBM Mid 70 Index.", "catalyst": "Mid-cap market momentum."}
}

def get_stock_data(ticker, period="1y"):
    """
    Fetches historical stock data from Yahoo Finance.
    Handles alternative symbols for futures and prioritizes knowledge base names.
    """
    ALT_SYMBOLS = {
        "FKLI=F": ["0001.KL", "FKLI=F", "KLI=F", "^KLCI"],
        "FCPO=F": ["CPO=F", "FCPO=F", "FCP.KL"],
        "FM70=F": ["^KL70", "FM70=F", "0002.KL"]
    }
    
    symbols_to_try = ALT_SYMBOLS.get(ticker, [ticker])
    
    # Prioritize name from knowledge base
    base_name = ticker
    if ticker in MARKET_INSIGHTS:
        base_name = MARKET_INSIGHTS[ticker]['name']
    
    for symbol in symbols_to_try:
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            if df.empty and period != "1mo":
                df = stock.history(period="1mo")
            
            if not df.empty:
                name = base_name
                # Only try yfinance info if we don't have a good name yet or if it's a new symbol
                if name == ticker or ".KL" in name:
                    try:
                        yf_info = stock.info
                        name = yf_info.get('shortName') or yf_info.get('longName') or name
                    except:
                        pass
                return df, name
        except Exception:
            continue
    return None, base_name

def analyze_breakout(ticker, df, resolved_name=None):
    """
    Performs technical breakout analysis.
    Returns a dictionary with results.
    """
    if df is None or len(df) < 50:
        return None

    current_price = df['Close'].iloc[-1]
    
    # Technical Indicators
    sma_20 = SMAIndicator(df['Close'], window=20).sma_indicator().iloc[-1]
    sma_50 = SMAIndicator(df['Close'], window=50).sma_indicator().iloc[-1]
    rsi = RSIIndicator(df['Close'], window=14).rsi().iloc[-1]
    
    # Breakout Logic:
    # 1. Price above SMA 20 and SMA 50
    # 2. Recent volume surge (e.g., today's volume > 1.5x 20-day average)
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
    
    # Qualitative Cross-Reference (Priority 1: Knowledge Base)
    insight = MARKET_INSIGHTS.get(ticker)
    if insight:
        name = insight["name"]
        code = insight["code"]
        analysis = insight["analysis"]
        catalyst = insight["catalyst"]
    else:
        # Priority 2: Resolved name from yfinance or symbol cleaning
        name = resolved_name or ticker.replace(".KL", "")
        code = ticker.split(".")[0]
        analysis = "Technical breakout analysis based on live data."
        catalyst = "Market momentum / Trend following."
    
    # Final name cleanup: If name is still a ticker code like "6888.KL", clean it
    if ".KL" in name and len(name) <= 10:
        name = name.replace(".KL", "")
    
    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "price": round(current_price, 3),
        "rsi": round(rsi, 2),
        "volume_surge": is_volume_surge,
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
    "FM70=F", # FTSE Bursa Malaysia Mid 70 Index Futures
    "FMG3=F", # 3-Year MGS Futures
    "FMG5=F"  # 5-Year MGS Futures
]

def get_futures_breakouts():
    """
    Specifically analyzes Malaysian Futures for breakouts.
    """
    results = []
    # Fetching individually for futures as they often have specific symbol issues
    for ticker in FUTURES_COMPONENTS:
        df, name = get_stock_data(ticker, period="1y")
        if df is not None and not df.empty:
            analysis = analyze_breakout(ticker, df, name)
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
        if df is not None and not df.empty:
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
