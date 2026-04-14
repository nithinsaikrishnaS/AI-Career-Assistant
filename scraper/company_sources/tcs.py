from scraper.base import BaseSource
from utils.browser import safe_run_playwright
from bs4 import BeautifulSoup

class TCSSource(BaseSource):
    def __init__(self):
        super().__init__("tcs")
        self.base_url = "https://ibegin.tcsapps.com/candidate/jobs/search"

    def _do_fetch(self, query="Software Engineer", limit=15) -> list:
        # TCS Discovery: Hardened iBegin Search (Fix 12)
        url = self.base_url
        self.logger.info(f"TCS: Starting interactive iBegin discovery for '{query}'")
        
        def run(page):
            # Navigate to iBegin
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Use the 'Keywords' field discovered in the audit
            try:
                # Wait for the search box (placeholder 'Skills, Designation, Role')
                page.wait_for_selector('input[placeholder*="Skills"]', timeout=30000)
                page.fill('input[placeholder*="Skills"]', query)
                
                # Click the 'Search Jobs' button
                page.click('button:has-text("Search Jobs"), input[value="Search Jobs"]')
                
                # Wait for results to populate
                page.wait_for_selector('.job-data-bar, .searched-job, .results-container', timeout=30000)
            except Exception as e:
                self.logger.warning(f"TCS: Interactive search timed out: {e}. Attempting DOM extraction anyway.")
            
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            postings = soup.select('.searched-job, .job-data-bar, .card')
            
            jobs = []
            for item in postings[:limit]:
                title_el = item.select_one('.job-info-title a, a.hand span, h3')
                link_el = item.select_one('a.hand, .job-info-title a')
                
                if title_el:
                    title = title_el.get_text(strip=True)
                    link = f"https://ibegin.tcsapps.com/candidate/jobs/search" # Default search fallback
                    if link_el:
                        h = link_el.get('href', '')
                        if h.startswith('http'): link = h

                    jobs.append({
                        "title": title, "company": "TCS", "location": "India",
                        "link": link, "source": self.name, "posted_at": "Today"
                    })
            return jobs

        return safe_run_playwright(run)

    def fetch_details(self, url):
        return {"description": "Full JD available on TCS iBegin portal."}
