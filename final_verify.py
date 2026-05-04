from bursa_core import get_top_breakouts, get_futures_breakouts
import sys

def verify():
    print("--- VERIFYING BURSA ANALYZER CORE ---")
    
    print("\n1. Testing KLCI Stock Name Resolution...")
    try:
        top_stocks = get_top_breakouts(limit=5)
        if top_stocks:
            for s in top_stocks:
                print(f"[OK] Stock Found: {s['code']} -> {s['name']} (Price: RM {s['price']}, Score: {s['score']}/5)")
        else:
            print("[FAIL] No stocks found in scan.")
    except Exception as e:
        print(f"[ERROR] Stock test failed: {e}")

    print("\n2. Testing Futures Data...")
    try:
        futures = get_futures_breakouts()
        if futures:
            for f in futures:
                print(f"[OK] Future Found: {f['ticker']} -> {f['name']} (Price: {f['price']}, Score: {f['score']}/5)")
        else:
            print("[FAIL] No futures data found.")
    except Exception as e:
        print(f"[ERROR] Futures test failed: {e}")

    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify()
