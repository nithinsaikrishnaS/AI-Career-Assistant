import sys
import os
import json

# Set up project path
sys.path.append('/Users/nithinsaikrishnas/Downloads/AI Projects')

from scraper.aggregator import JobAggregator

def run_diagnostic():
    print("🏁 [DIAGNOSTIC] Starting Scraper Reliability & Stabilization Audit\n" + "="*60)
    
    aggregator = JobAggregator()
    
    # Test only a subset for speed in diagnostic
    aggregator.company_sources = aggregator.company_sources[:2] # Microsoft, Amazon
    aggregator.platform_sources = [aggregator.platform_sources[0]] # Internshala
    aggregator.all_sources = aggregator.company_sources + aggregator.platform_sources
    
    jobs = aggregator.fetch_all(query="Software Developer", limit_per_source=5)
    
    print("\n📊 [HEALTH CHECK] Reading data/scraper_health.json...")
    try:
        with open("data/scraper_health.json", 'r') as f:
            health = json.load(f)
            for src, data in health.items():
                status = data.get('status', 'Unknown')
                count = data.get('count', 0)
                latency = data.get('latency', 'N/A')
                print(f"  - {src:15} | Status: {status} | Jobs: {count} | Latency: {latency}")
    except Exception as e:
        print(f"  ❌ Failed to read health file: {e}")

    print("\n🔬 [INTEGRITY CHECK] Validating Job Metadata...")
    if not jobs:
        print("  ❌ No jobs found across diagnostic sources.")
    else:
        sample = jobs[0]
        print(f"  - Sample Job: {sample.get('title')} @ {sample.get('company')}")
        
        # Check for mandatory fields
        required = ['title', 'company', 'link', 'source']
        missing = [f for f in required if not sample.get(f)]
        if missing:
            print(f"  ❌ Sample job missing fields: {missing}")
        else:
            print(f"  ✅ Metadata integrity verified.")

    print("\n" + "="*60 + "\n🎯 DIAGNOSTIC COMPLETE.")

if __name__ == "__main__":
    run_diagnostic()
