from playwright.sync_api import sync_playwright
from scraper.base import BaseSource
from bs4 import BeautifulSoup
import time

class AccentureSource(BaseSource):
    def __init__(self):
        super().__init__("accenture")
        # Updated to the specific Software Engineering India landing page for higher yield
        self.search_url = "https://www.accenture.com/in-en/careers/jobsearch?aoi=Software%20Engineering"

    def _do_fetch(self, query="Software Developer", limit=20) -> list:
        # Precision hardening for Accenture India portal (Fix 11)
        url = self.search_url
        self.logger.info(f"Accenture: Starting DOM discovery at {url}")
        
        jobs = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.headers["User-Agent"])
                
                # Navigate and wait for the job list card component
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for the explicit job card selector discovered in the audit
                try:
                    page.wait_for_selector('.rad-filters-vertical__job-card', timeout=30000)
                except:
                    self.logger.warning("Accenture: Job cards not found in time. Retrying with scroll.")
                
                # Scroll to trigger lazy loading of cards
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)
                
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Select the hardened job cards
                cards = soup.select('.rad-filters-vertical__job-card')
                
                for card in cards[:limit]:
                    title_el = card.select_one('.rad-filters-vertical__job-card-title')
                    link_el = card.find('a')
                    # Metadata found in spans (Location, Experience, etc)
                    meta_spans = card.select('span')
                    location = "India"
                    for span in meta_spans:
                        txt = span.get_text().strip()
                        if any(city in txt for city in ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Gurgaon", "Chennai"]):
                            location = txt
                            break
                    
                    if title_el and link_el:
                        title = title_el.get_text(strip=True)
                        link = link_el.get('href', '')
                        if link.startswith('/'):
                            link = "https://www.accenture.com" + link
                            
                        jobs.append({
                            "title": title,
                            "company": "Accenture",
                            "location": location,
                            "link": link,
                            "description": "High-priority Software Engineering role at Accenture India.",
                            "source": self.name,
                            "posted_at": "Today"
                        })
                
                browser.close()
                
            self.logger.info(f"Accenture: {len(jobs)} jobs discovered via DOM audit.")
            return jobs
        except Exception as e:
            self.logger.error(f"Accenture DOM audit failed: {e}")
            return []
