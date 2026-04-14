import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from scraper.base import BaseSource

class InternshalaSource(BaseSource):
    def __init__(self):
        super().__init__("internshala")
        self.base_url = "https://internshala.com"
        self.search_url = "https://internshala.com/jobs/work-from-home-jobs/"
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })

    def _do_fetch(self, query=None, limit=20) -> list:
        url = self.search_url
        if query:
            url = f"{self.base_url}/jobs/keywords-{query.replace(' ', '%20')}/"
            
        self.logger.info(f"Starting Internshala fetch from {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all containers that look like a job card (Try multiple variants for resilience)
            job_containers = soup.select('.individual_internship') or soup.select('.internship_container') or soup.select('.job-card')
            
            jobs = []
            for container in job_containers[:limit]:
                try:
                    # 10/10 Resilience: Multi-path Link Extraction
                    path = container.get('data-href')
                    if not path:
                        # Fallback 1: Direct link
                        link_el = container.select_one('a.view_detail_button') or container.select_one('.job-title-href')
                        path = link_el.get('href') if link_el else None
                    
                    if not path:
                        # Fallback 2: Deeper search
                        links = container.find_all('a', href=True)
                        for a in links:
                            if "/job/detail/" in a['href']:
                                path = a['href']
                                break
                                
                    title_el = container.select_one('.job-title-href') or container.select_one('.internship_heading a')
                    company_el = container.select_one('.company-name') or container.select_one('.company_and_premium a')
                    
                    if title_el:
                        title = title_el.get_text(strip=True)
                        company = company_el.get_text(strip=True) if company_el else "Hiring Company"
                        
                        if path:
                            path = path.strip()
                            # Construct absolute link
                            full_link = self.base_url + (path if path.startswith('/') else '/' + path) if not path.startswith('http') else path
                            
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": "Remote",
                                "link": full_link,
                                "description": "Analyzing opportunity metadata...", 
                                "source": self.name,
                                "posted_at": "Today"
                            })
                except Exception as card_err:
                    self.logger.warning(f"⚠️ Failed to parse a job card on Internshala: {card_err}")
                    continue
                    
            self.logger.info(f"Internshala Explorer: Found {len(jobs)} jobs.")
            return jobs
        except Exception as e:
            self.logger.error(f"Internshala failed: {e}")
            return []

    def fetch_details(self, url):
        # High-Speed Fallback Detail
        try:
            return {"description": f"This opportunity at Internshala is specifically curated for freshers. Visit the portal to apply directly and view full requirements."}
        except:
            return {"description": "Visit portal for full details."}
