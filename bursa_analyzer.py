import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
import datetime
from bursa_core import MARKET_INSIGHTS, get_stock_data, analyze_breakout

class BursaAnalyzer:
    def __init__(self, tickers):
        self.tickers = tickers
        self.results = []

    def run(self):
        print(f"\n--- BURSA MALAYSIA BREAKOUT ANALYZER ({datetime.date.today()}) ---")
        print(f"{'Code':<6} | {'Name':<12} | {'Price':<8} | {'Score':<5} | {'Deep Analysis'}")
        print("-" * 100)
        
        for ticker in self.tickers:
            df, resolved_name = get_stock_data(ticker)
            analysis = analyze_breakout(ticker, df, resolved_name)
            
            if analysis:
                print(f"{analysis['code']:<6} | {analysis['name']:<12} | {analysis['price']:<8} | {analysis['score']:<5} | {analysis['analysis']}")
                print(f"{'':<6} | {'':<12} | {'':<8} | {'':<5} | Catalyst: {analysis['catalyst']}")
                print("-" * 100)

if __name__ == "__main__":
    import sys
    
    # Use pre-defined watchlist by default
    watchlist = list(MARKET_INSIGHTS.keys())
    
    # If user provides custom codes in terminal: e.g. python bursa_analyzer.py 1023 5347
    if len(sys.argv) > 1:
        custom_tickers = []
        for arg in sys.argv[1:]:
            if ".KL" in arg or "=F" in arg or "^" in arg:
                custom_tickers.append(arg)
            else:
                custom_tickers.append(f"{arg}.KL")
        watchlist = custom_tickers

    analyzer = BursaAnalyzer(watchlist)
    analyzer.run()
