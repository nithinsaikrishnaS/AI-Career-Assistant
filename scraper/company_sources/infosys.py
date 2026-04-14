from playwright.sync_api import sync_playwright
from scraper.base import BaseSource
from bs4 import BeautifulSoup
import time

class InfosysSource(BaseSource):
    def __init__(self):
        super().__init__("infosys")
        # Global Careers portal search URL
        self.search_url = "https://digitalcareers.infosys.com/infosys/global-careers"

    def _do_fetch(self, query="Software Developer", limit=20) -> list:
        url = f"{self.search_url}?keyword={query.replace(' ', '%20')}&location=&template_id=1016&company_slug=infosys"
        self.logger.info(f"Starting Infosys Playwright fetch (JS-Dynamic): {query}")
        
        jobs = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.headers["User-Agent"])
                
                # Navigate and wait for content (Fix 3)
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(3) # Extra buffer for JS rendering
                
                # Extract rendered HTML
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Precision selectors discovered via DOM Audit (Fix 9)
                job_elements = soup.select('a.job')
                
                for item in job_elements[:limit]:
                    title_el = item.select_one('.job-title')
                    link = item.get('href', '')
                    loc_el = item.select_one('.location, .job-location')
                    
                    if title_el and link:
                        jobs.append({
                            "title": title_el.get_text(strip=True),
                            "company": "Infosys",
                            "location": loc_el.get_text(strip=True) if loc_el else "India",
                            "link": "https://digitalcareers.infosys.com" + link if link.startswith('/') else link,
                            "description": "Enterprise consulting and technology role at Infosys.",
                            "source": self.name
                        })
                
                browser.close()
                
            self.logger.info(f"Infosys: {len(jobs)} jobs discovered via dynamic rendering.")
            return jobs
        except Exception as e:
            self.logger.error(f"Infosys Playwright failed: {e}")
            return []
