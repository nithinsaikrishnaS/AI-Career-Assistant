from playwright.sync_api import sync_playwright
from scraper.base import BaseSource
from bs4 import BeautifulSoup
import time

class FreshersworldSource(BaseSource):
    def __init__(self):
        super().__init__("freshersworld")
        self.base_url = "https://www.freshersworld.com"

    def _do_fetch(self, query="Software Engineer", limit=20) -> list:
        # Precision hardening for Freshersworld following DOM audit (Fix 16)
        # Using the direct keyword search results URL found in the audit for maximum stability
        search_slug = query.lower().replace(" ", "-") if query else "software-engineer"
        url = f"{self.base_url}/jobs/jobsearch/{search_slug}-jobs"
        
        self.logger.info(f"Freshersworld: Starting DOM discovery at {url}")
        
        jobs = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                # Stealth-like context
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Navigate and wait for the main job wrapper
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for the explicit container discovered in the audit
                try:
                    # The audit confirmed .job-container is the key
                    page.wait_for_selector('.job-container', timeout=30000)
                except:
                    self.logger.warning("Freshersworld: Primary containers didn't load. Page might be restricted.")
                
                # Final scroll to trigger lazy loading
                page.evaluate("window.scrollBy(0, 1500)")
                time.sleep(2)
                
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Select the hardened job containers
                containers = soup.select('.job-container')
                
                for item in containers[:limit]:
                    title_el = item.select_one('.bold_font, span.wrap-title')
                    company_el = item.select_one('.company-name')
                    # Links often in <a> tags with specific text or classes
                    link_el = item.find('a', string=lambda t: t and ("View" in t or "Apply" in t)) or item.find('a', href=True)
                    location_el = item.select_one('.job-location')
                    
                    if title_el and company_el:
                        title = title_el.get_text(strip=True)
                        company = company_el.get_text(strip=True)
                        link = link_el['href'] if link_el else ""
                        if link and not link.startswith("http"):
                            link = self.base_url + link
                        
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location_el.get_text(strip=True) if location_el else "India",
                            "link": link,
                            "description": "Fresher-focused discovery via Freshersworld portal.",
                            "source": self.name,
                            "posted_at": "Today"
                        })
                
                browser.close()
                
            self.logger.info(f"Freshersworld: {len(jobs)} jobs discovered via direct search path.")
            return jobs
        except Exception as e:
            self.logger.error(f"Freshersworld DOM audit failed: {e}")
            return []
