import yfinance as yf
import pandas as pd
import os

# Set cache path
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path, exist_ok=True)
yf.set_tz_cache_location(cache_path)
os.environ['YFINANCE_CACHE_DIR'] = cache_path

FUTURES_COMPONENTS = [
    "FKLI=F", # FTSE Bursa Malaysia KLCI Futures
    "FCPO=F", # Crude Palm Oil Futures
    "FM70=F", # FTSE Bursa Malaysia Mid 70 Index Futures
    "FMG3=F", # 3-Year MGS Futures
    "FMG5=F"  # 5-Year MGS Futures
]

ALT_SYMBOLS = {
    "FKLI=F": ["FKLI=F", "^KLCI", "FKLIK26.KL", "FKLIM26.KL"],
    "FCPO=F": ["FCPO=F", "FCPON26.KL", "FCPOK26.KL", "FCPOM26.KL"],
    "FM70=F": ["FM70=F", "^KL70", "FM70K26.KL", "FM70M26.KL"]
}

print("--- DEBUGGING FUTURES FETCHING ---")

for ticker in FUTURES_COMPONENTS:
    print(f"\nChecking Ticker: {ticker}")
    symbols = ALT_SYMBOLS.get(ticker, [ticker])
    found = False
    for sym in symbols:
        print(f"  Trying Symbol: {sym}")
        try:
            stock = yf.Ticker(sym)
            df = stock.history(period="1y")
            if df.empty:
                df = stock.history(period="1mo")
            
            if not df.empty:
                print(f"  ✅ SUCCESS: {sym} | Price: {df['Close'].iloc[-1]:.2f} | Rows: {len(df)}")
                found = True
                break
            else:
                print(f"  ❌ EMPTY: {sym}")
        except Exception as e:
            print(f"  ❌ ERROR: {sym} | {e}")
    
    if not found:
        print(f"  ‼️ FAILED ALL SYMBOLS FOR {ticker}")

print("\n--- DEBUGGING COMPLETE ---")
