import logging
import json
import os
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from scraper.aggregator import aggregator
from matcher.engine import calculate_match, verify_job_quality, is_job_fresh, check_fresher_eligibility
from notifier.telegram import notifier
from utils.data_manager import (
    get_stored_profile, get_stored_preferences, get_seen_jobs, 
    save_seen_jobs, get_user_data, get_last_run, save_last_run
)
from utils import db_manager
from utils.state_manager import state_manager

# Configure focused logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutomationEngine")

IS_SCAN_ACTIVE = False # Global status for API
def run_job_pipeline():
    """Requirement 1: Consolidated Jobs Pipeline"""
    global IS_SCAN_ACTIVE
    if IS_SCAN_ACTIVE:
        logger.info("ℹ️ Scan already in progress. Skipping trigger.")
        return

    IS_SCAN_ACTIVE = True
    logger.info("🤖 Starting Automated Job Discovery Cycle...")
    state_manager.update("last_scheduler_run", time.time())
    state_manager.update("system_status", "Scraping")
    
    user_data = get_user_data()
    if not user_data:
        logger.warning("⚠️ Profile incomplete. Skipping automation.")
        state_manager.update("system_status", "Idle")
        IS_SCAN_ACTIVE = False
        return

    try:
        seen_links = db_manager.get_all_seen_links()
        ignored_links = db_manager.get_ignored_links() # Requirement 3: Adaptive filtering
        activity_history = db_manager.get_activity_history(limit=100) # Behavioral signal feed
        
        skills = user_data.get("skills", [])
        stream = "IT"
        user_role = user_data.get("role", "Software Developer")
        
        from matcher.engine import expand_role
        search_queries = expand_role(user_role)
        logger.info(f"🔍 Expanding Role Intelligence: '{user_role}' -> {search_queries}")
        
        # 1. Fetch Parallel
        raw_jobs = aggregator.fetch_all(search_queries, limit_per_source=25, seen_links=seen_links)
        total_fetched = len(raw_jobs)
        
        # 2. Process & 3. Detect New
        new_jobs_list = [j for j in raw_jobs if j.get('link') not in seen_links and j.get('link') not in ignored_links]
        
        state_manager.update("system_status", "Matching")
        new_rec = []
        new_oth = []
        rejected_count = 0
        
        for job in new_jobs_list:
            if job.get('source') in ["internshala", "accenture", "microsoft", "wellfound"]:
                try:
                    details = aggregator.fetch_details(job['source'], job['link'])
                    job.update(details)
                except Exception as e:
                    logger.warning(f"⚠️ Detail enrichment failed for {job.get('title')}: {e}")

            is_valid, reason = verify_job_quality(job, []) 
            if not is_valid: continue

            is_eligible, eligibility_reason = check_fresher_eligibility(job.get('title', ''), job.get('description', ''))
            if not is_eligible:
                rejected_count += 1
                continue

            posted_date = job.get('posted_at', 'Today')
            if not is_job_fresh(posted_date): 
                rejected_count += 1
                continue

            score, matched_skills, explanations, _ = calculate_match(
                job.get('title', ""), job.get('description', ""), job.get('location', ""),
                skills, stream, job.get('source', 'aggregator'), user_data, activity_history,
                job.get('posted_at', 'Today')
            )
            
            job.update({"score": score, "matched_skills": matched_skills, "explanation": explanations})
            
            if score >= 70:
                new_rec.append(job)
            else:
                new_oth.append(job)

        # 4. Save to DB
        db_manager.upsert_jobs(new_rec + new_oth)
        
        # Final observability summary
        logger.info(f"🏁 Cycle Complete: {len(new_rec)} Recommended | {len(new_oth)} Other | {rejected_count} Rejected")
        state_manager.update("recommended_last_run", len(new_rec))
        state_manager.update("rejected_last_run", rejected_count + len(new_oth))
        state_manager.update("last_match_time", time.time())
        state_manager.update("system_status", "Idle")
        
        # 5. Notify
        rec_with_ids = db_manager.get_jobs_by_links([j['link'] for j in new_rec])
        to_alert = [j for j in rec_with_ids if not j.get('sent_telegram')]
        notifier.send_summary({"total": total_fetched, "rec": len(new_rec), "others": len(new_oth)}, recommended_jobs=rec_with_ids, others=new_oth[:5])
        
        for job in to_alert:
            notifier.send_job_alert(job)
            db_manager.mark_as_sent(job['id'])
            
        # 6. Sync Seen
        for job in (new_rec + new_oth):
            db_manager.add_seen_link(job['link'])
        
        db_manager.save_db_last_run()
        db_manager.cleanup_old_jobs(days=30)
 
    except Exception as e:
        logger.error(f"❌ Automation failed: {e}")
        state_manager.update("system_status", "Error")
    finally:
        IS_SCAN_ACTIVE = False

def start_scheduler():
    """Final Production Assistant Scheduler"""
    scheduler = BackgroundScheduler()
    # 5-Hour Discovery Cycle
    scheduler.add_job(run_job_pipeline, 'interval', hours=5, next_run_time=datetime.now())
    # Daily Digest at 9:00 AM
    scheduler.add_job(run_daily_digest, 'cron', hour=9, minute=0)
    scheduler.start()
    logger.info("🚀 AI Assistant Scheduler Active [5h Cycle + 9AM Digest]")
    state_manager.update("scheduler_active", True)
    state_manager.update("system_status", "Idle")

def run_daily_digest():
    logger.info("🌅 Generating Daily Career Digest...")
    try:
        all_jobs = db_manager.get_all_jobs(limit=100)
        daily_top = [j for j in all_jobs if j.get('score', 0) >= 75]
        if not daily_top: return
        notifier.send_summary({"total": len(all_jobs), "rec": len(daily_top), "others": len(all_jobs) - len(daily_top)}, recommended_jobs=daily_top)
    except Exception as e:
        logger.error(f"❌ Digest failed: {e}")
