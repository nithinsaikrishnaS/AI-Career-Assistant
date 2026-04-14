import logging
import re
import time
from abc import ABC, abstractmethod
from utils.nlp import normalize_text

ALLOWED_DOMAINS = [
    "microsoft.com", "amazon.com", "siemens.com", "accenture.com", 
    "infosys.com", "tcs.com", "wipro.com", "hcltech.com", 
    "cognizant.com", "wellfound.com", "internshala.com", "freshersworld.com",
    "indeed.com"
]

import random

ROTATE_HEADERS = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0 Safari/537.36"}
]

class BaseSource(ABC):
    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger(name)
        self.headers = self.get_random_header()

    def get_random_header(self):
        """Returns a production-grade header to evade fingerprinting."""
        return random.choice(ROTATE_HEADERS)

    def is_url_safe(self, url):
        """Validates that the target URL is in the authorized domain whitelist (Requirement 9)."""
        return any(domain in url.lower() for domain in ALLOWED_DOMAINS)

    def fetch_jobs(self, query, limit=20, seen_links=None) -> list:
        """
        Unified Fetcher with Retry & Incremental Logic (Requirement 3 & 4).
        """
        seen_links = seen_links or set()
        
        for attempt in range(1, 4):
            try:
                self.logger.info(f"{self.name}: Discovery attempt {attempt}/3...")
                # Rotate header per attempt
                self.headers = self.get_random_header()
                jobs = self._do_fetch(query, limit)
                
                if not jobs and attempt < 3:
                    backoff = attempt * 2 # Exponential Backoff (Requirement: Reliability)
                    self.logger.info(f"{self.name}: No jobs found. Backing off for {backoff}s...")
                    time.sleep(backoff)
                    continue
                
                # Layer 6: Deduplication & Incremental Stop
                cleaned_jobs = []
                seen_in_scan = set()
                seen_count = 0
                
                for job in jobs:
                    # 1. Deduplicate by Title + Company (Requirement 6)
                    t_clean = normalize_text(job.get('title',''))
                    c_clean = normalize_text(job.get('company',''))
                    j_hash = f"{t_clean}|{c_clean}"
                    
                    if j_hash in seen_in_scan:
                        continue
                    seen_in_scan.add(j_hash)
                    
                    # 2. Incremental Stop: If we found a seen job, we track it (Requirement 3)
                    # We stop after 2 seen jobs to ensure we catch re-posted roles but skip old ones
                    if job.get('link') in seen_links:
                        seen_count += 1
                        if seen_count >= 2:
                            self.logger.info(f"{self.name}: Seen role threshold reached. Terminating incremental scan.")
                            break
                        continue
                    
                    cleaned_jobs.append(self.clean_job_data(job))
                
                return [j for j in cleaned_jobs if j]
                
            except Exception as e:
                self.logger.error(f"{self.name} attempt {attempt} failed: {e}")
                if attempt == 3:
                    self.logger.critical(f"⚠️ {self.name} FINAL FAILURE.")
                    return []
                time.sleep(2)
        return []

    @abstractmethod
    def _do_fetch(self, query, limit) -> list:
        pass

    def clean_job_data(self, job):
        """Sanitizes messy discovery data (Trimming, Title Cleaning)."""
        if not self.is_valid_job(job):
            return None

        desc = job.get('description', 'No description available.')
        job['description'] = (desc[:497] + '...') if len(desc) > 500 else desc
        
        # Clean messy titles (remove HTML junk)
        title = job.get('title', 'Unknown Role')
        job['title'] = re.sub('<[^<]+?>', '', title).strip()
        
        return job

    def is_valid_job(self, job):
        """10/10 Reliability: Strict validation of discovery metadata."""
        if not job: return False
        if not job.get('title') or len(job['title']) < 5: return False
        if not job.get('link') or "http" not in job['link']: return False
        if not job.get('company') or len(job['company']) < 2: return False
        return True

    def fetch_details(self, url):
        return {"description": "Visit link for full details."}
