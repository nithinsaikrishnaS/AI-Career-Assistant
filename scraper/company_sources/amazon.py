import requests
from scraper.base import BaseSource

class AmazonSource(BaseSource):
    def __init__(self):
        super().__init__("amazon")
        self.api_url = "https://www.amazon.jobs/en/search.json"

    def _do_fetch(self, query=None, limit=20) -> list:
        # Amazon Jobs public API - Verified Parameters
        # Using 'normalized_country_code[]=IND' instead of location string for precision
        params = {
            "result_limit": limit,
            "sort": "recent",
            "category[]": "software-development",
            "normalized_country_code[]": "IND",
            "base_query": query or "Software Developer"
        }
        
        self.logger.info(f"Amazon: Fetching Indian jobs for '{query}' using IND country code")
        
        try:
            response = requests.get(self.api_url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                jobs_data = data.get('jobs', [])
                
                results = []
                for j in jobs_data:
                    results.append({
                        "title": j.get('title'),
                        "company": "Amazon",
                        "location": j.get('location', 'India'),
                        "link": "https://www.amazon.jobs" + j.get('job_path', ''),
                        "description": j.get('description_short', 'SDE role at Amazon India.'),
                        "source": self.name,
                        "posted_at": j.get('posted_date', 'Today')
                    })
                self.logger.info(f"Amazon: Found {len(results)} jobs.")
                return results
            else:
                self.logger.warning(f"Amazon API returned status {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"Amazon fetch failed: {e}")
            return []
