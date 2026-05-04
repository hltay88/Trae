import yfinance as yf
s = yf.Ticker("FBM70.FGI")
df = s.history(period="1y")
print(f"Rows for 1y: {len(df)}")
df = s.history(period="max")
print(f"Rows for max: {len(df)}")
