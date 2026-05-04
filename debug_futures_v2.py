import yfinance as yf
import pandas as pd
import os
import sys

# Set cache path
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path, exist_ok=True)
yf.set_tz_cache_location(cache_path)
os.environ['YFINANCE_CACHE_DIR'] = cache_path

FUTURES_COMPONENTS = [
    "FKLI=F", 
    "FCPO=F", 
    "FM70=F"
]

ALT_SYMBOLS = {
    "FKLI=F": ["FKLI=F", "^KLCI", "FKLIK26.KL", "FKLIM26.KL"],
    "FCPO=F": ["FCPO=F", "FCPON26.KL", "FCPOK26.KL", "FCPOM26.KL"],
    "FM70=F": ["FM70=F", "^KL70", "FM70K26.KL", "FM70M26.KL"]
}

print("--- STARTING DEBUG ---")

for ticker in FUTURES_COMPONENTS:
    print(f"Checking {ticker}...")
    symbols = ALT_SYMBOLS.get(ticker, [ticker])
    for sym in symbols:
        try:
            print(f"  Fetching {sym}...")
            s = yf.Ticker(sym)
            df = s.history(period="1mo")
            if not df.empty:
                print(f"  SUCCESS: {sym} Price={df['Close'].iloc[-1]}")
                break
            else:
                print(f"  EMPTY: {sym}")
        except Exception as e:
            print(f"  ERROR: {sym} -> {e}")

print("--- DEBUG END ---")
