import yfinance as yf
import requests

def search_yf(q):
    print(f"Searching for: {q}")
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=10"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers).json()
        for q in res.get('quotes', []):
            print(f"  - Symbol: {q['symbol']} | Name: {q.get('shortname')} | Type: {q.get('quoteType')}")
    except Exception as e:
        print(f"Error searching: {e}")

search_yf("Crude Palm Oil")
search_yf("FKLI")
search_yf("FCPO")
