import requests
import json
import logging
from scraper.base import BaseSource

class CognizantSource(BaseSource):
    def __init__(self):
        super().__init__("cognizant")
        self.base_url = "https://careers.cognizant.com"
        # Phenom People API endpoint (typically)
        self.api_url = "https://careers.cognizant.com/api/jobs"

    def _do_fetch(self, query=None, limit=10) -> list:
        # Phenom People API often accepts POST with JSON criteria
        payload = {
            "from": 0,
            "size": limit,
            "q": query or "Software Developer",
            "location": "India",
            "category": [],
            "job_type": []
        }
        
        self.logger.info(f"Cognizant: Fetching jobs for '{query}'")
        
        try:
            # Note: In a real enterprise env, we might need specific Phenom headers (CSRF, etc.)
            # If API is blocked, we fallback to Playwright in the aggregator.
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                jobs_data = data.get('jobs', [])
                
                results = []
                for j in jobs_data:
                    results.append({
                        "title": j.get('title'),
                        "company": "Cognizant",
                        "location": j.get('location', 'India'),
                        "link": self.base_url + "/global/en/job/" + j.get('jobId', ''),
                        "description": j.get('description', 'Role at Cognizant.'),
                        "source": self.name,
                        "posted_at": j.get('postedDate', 'Today')
                    })
                return results
            
            # Fallback for simple discovery
            return []
        except Exception as e:
            self.logger.error(f"Cognizant fetch failed: {e}")
            return []

    def fetch_details(self, url):
        return {"description": "Full details available at Cognizant's Phenom-powered career portal."}
