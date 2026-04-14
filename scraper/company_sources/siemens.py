import requests
import urllib3
from scraper.base import BaseSource

# Suppress SSL warnings for Siemens portal cert issues (Fix 1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SiemensSource(BaseSource):
    def __init__(self):
        super().__init__("siemens")
        self.api_url = "https://jobs.siemens.com/api/v1/jobs"

    def _do_fetch(self, query="Software Developer", limit=20) -> list:
        # Siemens specific API parameters
        params = {
            "query": query,
            "location": "India",
            "page": 1,
            "limit": limit,
            "project_category": "Software" # Narrow fetch to tech
        }
        
        self.logger.info(f"Starting Siemens API fetch: {query}")
        
        try:
            # Fix 1: Handle potential cert blocking with verify=False, Increase timeout for India portal
            response = requests.get(self.api_url, params=params, headers=self.headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                self.logger.warning(f"Siemens API returned {response.status_code}")
                return []
                
            data = response.json()
            jobs = []
            
            postings = data.get('jobs', [])
            for item in postings:
                jobs.append({
                    "title": item.get('title'),
                    "company": "Siemens",
                    "location": item.get('location', {}).get('name', "India"),
                    "link": f"https://jobs.siemens.com/jobs/{item.get('id')}",
                    "description": "Innovative engineering and software development roles.",
                    "source": self.name,
                    "posted_at": item.get('posted', "Unknown Date")
                })
                
            self.logger.info(f"Siemens: {len(jobs)} jobs fetched.")
            return jobs
        except Exception as e:
            self.logger.error(f"Siemens failed: {e}")
            return []
