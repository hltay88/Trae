import yfinance as yf
import os

# Redirect cache
cache_path = os.path.join(os.getcwd(), ".yfinance_cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path, exist_ok=True)
try:
    yf.set_tz_cache_location(cache_path)
except:
    pass
os.environ['YFINANCE_CACHE_DIR'] = cache_path

s = yf.Ticker("FBM70.FGI")
df = s.history(period="1mo")
print(df[['Close', 'Volume']].tail())
