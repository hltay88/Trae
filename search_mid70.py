import requests
url = "https://query2.finance.yahoo.com/v1/finance/search?q=Bursa Malaysia Mid 70&quotesCount=10"
headers = {'User-Agent': 'Mozilla/5.0'}
res = requests.get(url, headers=headers).json()
for q in res.get('quotes', []):
    print(f"Symbol: {q['symbol']} | Name: {q.get('shortname')}")
