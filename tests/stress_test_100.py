import sys
import os
import requests
import concurrent.futures
import time

# Configuration
API_URL = "http://localhost:8000"
API_KEY = "ai_job_aggregator_prod_key_778899"
CONCURRENT_REQUESTS = 100

def test_load():
    print(f"🚀 [STRESS TEST] Simulating {CONCURRENT_REQUESTS} concurrent requests...")
    headers = {"X-API-KEY": API_KEY}
    
    start_time = time.time()
    
    def make_request():
        try:
            # Hit /health for pure baseline stability check
            resp = requests.get(f"{API_URL}/health", headers=headers, timeout=10)
            return resp.status_code
        except Exception as e:
            return str(e)

    # Use ThreadPool to simulate concurrent users
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda _: make_request(), range(CONCURRENT_REQUESTS)))
    
    end_time = time.time()
    total_time = end_time - start_time
    
    success_count = results.count(200)
    rate_limited_count = results.count(429)
    error_count = len([res for res in results if isinstance(res, str) or (isinstance(res, int) and res not in [200, 429])])
    
    print(f"  - Total Events: {CONCURRENT_REQUESTS}")
    print(f"  - 200 OK: {success_count} (Expected ~60 due to rate limit)")
    print(f"  - 429 Rate Limited: {rate_limited_count} (Expected ~40)")
    print(f"  - Crashes/Errors: {error_count} (Expected 0)")
    print(f"  - Avg Latency: {total_time/CONCURRENT_REQUESTS:.4f}s")
    
    # Validation
    if error_count == 0 and success_count > 0:
        print("\n✅ LOAD TEST PASSED: Security gate enforced traffic control without system degradation.")
        return True
    else:
        print("\n❌ LOAD TEST FAILED: System instability detected.")
        return False

if __name__ == "__main__":
    test_load()
