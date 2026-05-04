import yfinance as yf
import pandas as pd
import os

# Set cache path
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path, exist_ok=True)
yf.set_tz_cache_location(cache_path)
os.environ['YFINANCE_CACHE_DIR'] = cache_path

symbols = ["^KLSE", "FCPON26.KL", "FBM70.FGI"]

print("--- TESTING SYMBOLS V5 ---")

for sym in symbols:
    print(f"Checking {sym}...")
    try:
        s = yf.Ticker(sym)
        df = s.history(period="5d")
        if not df.empty:
            print(f"  SUCCESS: {sym} Price={df['Close'].iloc[-1]}")
        else:
            print(f"  EMPTY: {sym}")
    except Exception as e:
        print(f"  ERROR: {sym} -> {e}")

print("--- TEST END ---")
