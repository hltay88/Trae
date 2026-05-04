import bursa_core

print("Testing get_futures_breakouts...")
results = bursa_core.get_futures_breakouts()
if results:
    for r in results:
        print(f"SUCCESS: {r['name']} ({r['ticker']}) Price: {r['price']}")
else:
    print("FAILED: No futures data found.")
