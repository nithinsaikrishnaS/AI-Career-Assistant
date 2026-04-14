import logging
import os
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.nlp import normalize_text

# Import modular sources
from scraper.internshala import InternshalaSource
from scraper.freshersworld import FreshersworldSource
from scraper.company_sources.infosys import InfosysSource
from scraper.company_sources.accenture import AccentureSource
from scraper.company_sources.microsoft import MicrosoftSource
from scraper.company_sources.siemens import SiemensSource
from scraper.company_sources.amazon import AmazonSource
from scraper.company_sources.tcs import TCSSource
from scraper.company_sources.wipro import WiproSource
from scraper.company_sources.hcltech import HCLTechSource
from scraper.company_sources.cognizant import CognizantSource
from scraper.wellfound import WellfoundSource

HEALTH_FILE = "data/scraper_health.json"

class JobAggregator:
    def __init__(self):
        self.logger = logging.getLogger("JobAggregator")
        
        # Priority 1: Company Sources
        self.company_sources = [
            MicrosoftSource(), AmazonSource(), SiemensSource(), 
            AccentureSource(), InfosysSource(), TCSSource(), 
            WiproSource(), HCLTechSource(), CognizantSource()
        ]
        
        # Priority 2: Platform Sources
        self.platform_sources = [
            InternshalaSource(), FreshersworldSource(), WellfoundSource()
        ]
        
        self.all_sources = self.company_sources + self.platform_sources

    def fetch_all(self, queries=["Software Developer"], limit_per_source=20, seen_links=None):
        """
        Mult-Query Role Intelligence Fetcher (Requirement 4).
        """
        if isinstance(queries, str): queries = [queries]
        
        seen_links = seen_links or set()
        all_jobs = []
        health_status = {}
        
        from utils.state_manager import state_manager
        state_manager.update("system_status", "Scraping")
        
        for query in queries:
            self.logger.info(f"🔍 Executing '{query}' Scan...")
            # Unified execution with Priority Scoring & Wave Isolation
            for layer_name, sources in [("Company", self.company_sources), ("Platform", self.platform_sources)]:
                with ThreadPoolExecutor(max_workers=min(len(sources), 10)) as executor:
                    future_to_source = {
                        executor.submit(src.fetch_jobs, query, limit_per_source, seen_links): src.name 
                        for src in sources
                    }
                    
                    for future in as_completed(future_to_source):
                        source_name = future_to_source[future]
                        try:
                            jobs = future.result()
                            if jobs:
                                self.logger.info(f"✅ {source_name:15} | Found {len(jobs)} jobs")
                                all_jobs.extend(jobs)
                            else:
                                self.logger.debug(f"ℹ️ {source_name:15} | No new jobs found")
                        except Exception as e:
                            self.logger.error(f"❌ Source failure [{source_name}]: {e}")
        
        # Global Semantic Deduplication
        unique_jobs = []
        global_seen = set()
        for job in all_jobs:
            if job.get('link') not in global_seen:
                unique_jobs.append(job)
                global_seen.add(job.get('link'))

        if len(unique_jobs) == 0:
            self.logger.warning("⚠️ No jobs fetched — possible scraper failure or query mismatch")
        else:
            self.logger.info(f"🏁 Discovery Complete. Total unique jobs: {len(unique_jobs)}")

        state_manager.update("last_scrape_time", time.time())
        state_manager.update("jobs_scraped_last_run", len(unique_jobs))
        state_manager.update("system_status", "Idle")
        
        return unique_jobs

    def fetch_details(self, source_name, url):
        for source in self.all_sources:
            if source.name == source_name:
                return source.fetch_details(url)
        return {"description": "Visit link for full details."}

aggregator = JobAggregator()
