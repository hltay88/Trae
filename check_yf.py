import yfinance as yf
import os

# Set a concrete path for cache
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

try:
    yf.set_tz_cache_location(cache_path)
    print(f"Cache location set to: {cache_path}")
except Exception as e:
    print(f"Warning: Could not set tz cache location: {e}")

os.environ['YFINANCE_CACHE_DIR'] = cache_path

try:
    print("Fetching data for 1155.KL...")
    stock = yf.Ticker("1155.KL")
    df = stock.history(period="1mo")
    if df.empty:
        print("Data is empty!")
    else:
        print(f"Data for 1155.KL fetched successfully:\n{df.tail()}")
except Exception as e:
    print(f"Error fetching data: {e}")
    import traceback
    traceback.print_exc()
