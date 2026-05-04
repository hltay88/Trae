import yfinance as yf
import os

# Set a concrete path for cache
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

try:
    yf.set_tz_cache_location(cache_path)
except Exception:
    pass

os.environ['YFINANCE_CACHE_DIR'] = cache_path

# Extended search for FKLI and FCPO
test_symbols = [
    "FKLI=F", "KLI=F", "^KLCI", "0001.KL", "KLCI.KL", 
    "FCPO=F", "CPO=F", "FCP.KL", "MYR=X"
]

for symbol in test_symbols:
    try:
        print(f"Testing {symbol}...")
        stock = yf.Ticker(symbol)
        df = stock.history(period="1mo")
        if not df.empty:
            print(f"OK: {symbol} has data. Last close: {df['Close'].iloc[-1]}")
        else:
            print(f"FAIL: {symbol} returned empty data.")
    except Exception as e:
        print(f"ERR with {symbol}: {str(e)}")
    print("-" * 20)
