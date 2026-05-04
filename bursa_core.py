import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import datetime
import requests

# Disable yfinance cache to avoid database errors
try:
    import yfinance.cache as yf_cache
    yf_cache.enabled = False
except Exception:
    pass

# --- KNOWLEDGE BASE: LATEST MARKET INSIGHTS (MAY 2026) ---
MARKET_INSIGHTS = {
    "1155.KL": {
        "code": "1155",
        "name": "MAYBANK",
        "sector": "Banking",
        "analysis": "Strong defensive play with attractive dividends. Stable base for FBM KLCI.",
        "catalyst": "High interest rate environment and digital banking growth."
    },
    "5347.KL": {
        "code": "5347",
        "name": "TNB",
        "sector": "Utilities",
        "analysis": "Top pick for FY26. Grid investments and renewable energy leadership.",
        "catalyst": "National Energy Transition Roadmap (NETR) and rising regulated asset base."
    },
    "5246.KL": {
        "code": "5246",
        "name": "WESTPORTS",
        "sector": "Transportation",
        "analysis": "Proxy for global trade recovery. Tariff revisions improve margins.",
        "catalyst": "Normalization of global trade and resilient intra-Asia volumes."
    },
    "7148.KL": {
        "code": "7148",
        "name": "DPHARMA",
        "sector": "Healthcare",
        "analysis": "Margin expansion due to stronger Ringgit (lower import costs for APIs).",
        "catalyst": "Increased public healthcare spending and medical tourism surge."
    },
    "5099.KL": {
        "code": "5099",
        "name": "CAPITALA",
        "sector": "Aviation/Tourism",
        "analysis": "Primary proxy for Visit Malaysia Year 2026 (VMY2026). Formerly AirAsia.",
        "catalyst": "Tourism surge and improved flight connectivity."
    },
    "1023.KL": {
        "code": "1023",
        "name": "CIMB",
        "sector": "Banking",
        "analysis": "Leading ASEAN focused bank. Strong earnings growth and ROE expansion.",
        "catalyst": "Normalization of credit costs and strong non-interest income growth."
    },
    "1082.KL": {
        "code": "1082",
        "name": "HLFG",
        "sector": "Banking",
        "analysis": "Undervalued financial holding company. Strong contribution from Hong Leong Bank.",
        "catalyst": "Undemanding price-to-book value and strong asset quality of subsidiaries."
    },
    "FKLI=F": {
        "code": "FKLI",
        "name": "KLCI FUTURES",
        "sector": "Futures",
        "analysis": "Proxy for the underlying FBM KLCI index.",
        "catalyst": "Market sentiment and index component performance."
    },
    "FCPO=F": {
        "code": "FCPO",
        "name": "CPO FUTURES",
        "sector": "Futures",
        "analysis": "Global benchmark for Crude Palm Oil prices.",
        "catalyst": "Supply/demand in edible oils and biodiesel policy."
    },
    "FM70=F": {
        "code": "FM70",
        "name": "MID 70 FUTURES",
        "sector": "Futures",
        "analysis": "Proxy for the FBM Mid 70 Index.",
        "catalyst": "Mid-cap market momentum."
    }
}

def get_stock_data(ticker, period="1y"):
    """
    Fetches historical stock data from Yahoo Finance.
    Handles alternative symbols for futures.
    """
    ALT_SYMBOLS = {
        "FKLI=F": ["FKLI=F", "KLI=F", "^KLCI"],
        "FCPO=F": ["FCPO=F", "CPO=F", "FCP.KL"]
    }
    
    symbols_to_try = ALT_SYMBOLS.get(ticker, [ticker])
    
    for symbol in symbols_to_try:
        try:
            # Using yfinance's Ticker directly without explicit session
            # but ensuring we don't use cache if possible
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            if df.empty and period != "1mo":
                df = stock.history(period="1mo")
            
            if not df.empty:
                name = symbol
                try:
                    name = stock.info.get('shortName') or stock.info.get('longName') or symbol
                except:
                    if ticker in MARKET_INSIGHTS:
                        name = MARKET_INSIGHTS[ticker]['name']
                return df, name
        except Exception:
            continue
    return None, ticker

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
    
    # Qualitative Cross-Reference
    insight = MARKET_INSIGHTS.get(ticker)
    if insight:
        name = insight["name"]
        code = insight["code"]
        analysis = insight["analysis"]
        catalyst = insight["catalyst"]
    else:
        name = resolved_name or ticker.replace(".KL", "")
        code = ticker.split(".")[0]
        analysis = "Technical breakout analysis based on live data."
        catalyst = "Market momentum / Trend following."
    
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
