import requests
from bs4 import BeautifulSoup
import logging
from scraper.base import BaseSource

class HCLTechSource(BaseSource):
    def __init__(self):
        super().__init__("hcltech")
        self.base_url = "https://careers.hcltech.com"

    def _do_fetch(self, query=None, limit=10) -> list:
        search_query = query.replace(" ", "%20") if query else "Software%20Developer"
        # HCLTech public search URL
        url = f"{self.base_url}/search-jobs/{search_query}"
        
        self.logger.info(f"HCLTech: Fetching jobs for '{query}'")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            jobs = []
            # SuccessFactors / Phenom hybrid pattern
            for item in soup.select('.job-title, [data-ph-at-id="job-title-link"]'):
                if len(jobs) >= limit: break
                
                title = item.get_text(strip=True)
                link = item.get('href')
                if not title or not link: continue
                
                if not link.startswith("http"):
                    link = self.base_url + link
                    
                jobs.append({
                    "title": title,
                    "company": "HCLTech",
                    "location": "India",
                    "link": link,
                    "description": "Opportunity at HCLTech. Details available on the career portal.",
                    "source": self.name,
                    "posted_at": "Today"
                })
                
            return jobs
        except Exception as e:
            self.logger.error(f"HCLTech fetch failed: {e}")
            return []

    def fetch_details(self, url):
        return {"description": "Visit HCLTech recruitment portal for full job specifications."}
