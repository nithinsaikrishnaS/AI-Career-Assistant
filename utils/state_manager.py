import time
import json
import os
from datetime import datetime

STATE_FILE = "data/system_state.json"

class SystemState:
    def __init__(self):
        self.state = {
            "last_scrape_time": "Never",
            "last_match_time": "Never",
            "last_telegram_time": "Never",
            "last_scheduler_run": "Never",
            "system_status": "Idle", # Idle, Scraping, Matching, Processing
            "scheduler_active": True,
            "jobs_scraped_last_run": 0,
            "recommended_last_run": 0,
            "rejected_last_run": 0,
            "total_jobs_in_db": 0
        }
        self.load()

    def load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    saved = json.load(f)
                    self.state.update(saved)
            except:
                pass

    def save(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=4)
        except:
            pass

    def update(self, key, value):
        if key == "last_scrape_time" or key == "last_match_time" or key == "last_telegram_time" or key == "last_scheduler_run":
            # Convert timestamp to human readable if it's a float
            if isinstance(value, (int, float)):
                value = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
        
        self.state[key] = value
        self.save()

    def get(self, key):
        return self.state.get(key)

    def get_all(self):
        return self.state

state_manager = SystemState()
