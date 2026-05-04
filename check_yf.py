import yfinance as yf
try:
    stock = yf.Ticker("1155.KL")
    df = stock.history(period="1mo")
    print(f"Data for 1155.KL:\n{df.tail()}")
except Exception as e:
    print(f"Error: {e}")
