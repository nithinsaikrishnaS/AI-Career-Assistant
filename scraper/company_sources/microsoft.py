from scraper.base import BaseSource
from utils.browser import safe_run_playwright
from bs4 import BeautifulSoup

class MicrosoftSource(BaseSource):
    def __init__(self):
        super().__init__("microsoft")

    def _do_fetch(self, query="Software Developer", limit=20) -> list:
        url = f"https://apply.careers.microsoft.com/careers?query={query.replace(' ', '%20')}&location=India"
        
        def run(page):
            self.logger.info(f"Microsoft: Discovery at {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector('a[id*="job-card-"]', timeout=20000)
            
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            job_elements = soup.select('a[id*="job-card-"]')
            
            discovery = []
            for item in job_elements[:limit]:
                title_el = item.select_one('div > div > div')
                title = title_el.get_text(strip=True) if title_el else "Software Engineering Role"
                link_path = item.get('href', '')
                link = f"https://apply.careers.microsoft.com{link_path}" if link_path.startswith('/') else link_path
                location_el = item.select_one('div[class*="fieldValue"]')
                location = location_el.get_text(strip=True) if location_el else "Remote/Global"
                
                discovery.append({
                    "title": title, "company": "Microsoft", "location": location,
                    "link": link, "source": self.name, "posted_at": "New"
                })
            return discovery

        return safe_run_playwright(run)
                
    def fetch_details(self, url: str) -> dict:
        def run(page):
            self.logger.info(f"Microsoft: Deep-Scan at {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector('div[class*="description"]', timeout=10000)
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            desc_el = soup.select_one('div[class*="description"]')
            description = desc_el.get_text(separator=' ', strip=True) if desc_el else ""
            return {"description": description}

        try:
            return safe_run_playwright(run)
        except Exception as e:
            self.logger.error(f"Microsoft Deep-Scan failed: {e}")
            return {"description": "Visit link for full details."}
