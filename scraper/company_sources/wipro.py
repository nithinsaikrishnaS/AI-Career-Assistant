from scraper.base import BaseSource
from utils.browser import safe_run_playwright
from bs4 import BeautifulSoup

class WiproSource(BaseSource):
    def __init__(self):
        super().__init__("wipro")
        self.base_url = "https://careers.wipro.com/careers-home/jobs"

    def _do_fetch(self, query=None, limit=10) -> list:
        search_url = f"{self.base_url}?keyword={query or 'Software Developer'}&location=India"
        
        def run(page):
            self.logger.info(f"Wipro: Discovery at {search_url}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector('li[class*="JobsList_jobCard__"]', timeout=30000)
            
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            items = soup.select('li[class*="JobsList_jobCard__"]')
            
            jobs = []
            for item in items[:limit]:
                link_el = item.select_one('a.jobCardTitle')
                if not link_el: continue
                title = link_el.get_text(strip=True)
                link = link_el.get('href', '')
                if not title or not link or len(title) < 5: continue
                if not link.startswith("http"):
                    link = "https://careers.wipro.com" + link
                
                jobs.append({
                    "title": title, "company": "Wipro", "location": "India",
                    "link": link, "source": self.name, "posted_at": "Today"
                })
            return jobs

        return safe_run_playwright(run)
