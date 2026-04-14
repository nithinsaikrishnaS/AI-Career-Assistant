import sqlite3
import json
import os
from datetime import datetime

from .logger import get_logger

DB_FILE = "data/jobs.db"
logger = get_logger("DBManager")

def get_connection():
    # check_same_thread=False needed for SQLite + FastAPI/Threading
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 10/10 Hardening: Enable WAL Mode for high concurrency
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception as e:
        logger.warning(f"⚠️ Could not enable WAL mode: {e}")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        location TEXT,
        link TEXT UNIQUE,
        description TEXT,
        source TEXT,
        score INTEGER,
        matched_skills TEXT,
        explanation TEXT,
        posted_at TEXT,
        sent_telegram INTEGER DEFAULT 0,
        discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Auto-migration for existing DBs (Fix 34 - Schema Evolution)
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN explanation TEXT")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN sent_telegram INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    
    # 2. Seen Jobs (Deduplication)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_jobs (
        link TEXT PRIMARY KEY,
        discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. User Profile
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1), 
        role TEXT,
        location TEXT,
        domain TEXT,
        skills TEXT
    )
    """)
    
    # 4. Applications Tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        status TEXT DEFAULT 'Interested', 
        applied_date TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )
    """)

    # 6. User Activity / Behavioral Signals (Requirement 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        activity_type TEXT, -- 'view', 'apply', 'ignore'
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )
    """)
    
    # 7. Settings Table (for last_run_time, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # 8. Production Indices (Requirement 5: Scalability)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_discovery ON jobs(discovery_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type)")
    
    conn.commit()
    conn.close()

# --- Jobs CRUD ---

def upsert_jobs(jobs_list):
    """Saves jobs with transaction safety and loop isolation."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            for job in jobs_list:
                try:
                    cursor.execute("""
                    INSERT INTO jobs (
                        title, company, location, link, description, source, score, matched_skills, explanation, posted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        title=excluded.title,
                        company=excluded.company,
                        description=excluded.description,
                        score=excluded.score,
                        matched_skills=excluded.matched_skills,
                        explanation=excluded.explanation,
                        discovery_date=CURRENT_TIMESTAMP
                    """, (
                        job.get('title'), job.get('company'), job.get('location'), job.get('link'),
                        job.get('description'), job.get('source'), job.get('score'),
                        json.dumps(job.get('matched_skills', [])),
                        json.dumps(job.get('explanation', [])),
                        job.get('posted_at')
                    ))
                except Exception as loop_err:
                    logger.error(f"⚠️ Skipping corrupted job {job.get('link', 'unknown')}: {str(loop_err)}")
                    continue
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Transaction failure in upsert_jobs: {str(e)}")
        raise e

def get_all_jobs(limit=200):
    conn = get_connection()
    cursor = conn.cursor()
    # Sort by score first, then by the most recent discovery
    cursor.execute("SELECT * FROM jobs ORDER BY score DESC, discovery_date DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    jobs = []
    for row in rows:
        job = dict(row)
        job['matched_skills'] = json.loads(job['matched_skills']) if job['matched_skills'] else []
        job['explanation'] = json.loads(job['explanation']) if job.get('explanation') else []
        jobs.append(job)
    return jobs

def recalculate_all_scores(recalc_func, user_data, activity_history):
    """Refreshes all stored job scores with transactional safety."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, description, location, source, posted_at FROM jobs")
            rows = cursor.fetchall()
            
            updated_count = 0
            for i, row in enumerate(rows):
                try:
                    score, matched_skills, explanations, _ = recalc_func(
                        row['title'], row['description'], row['location'],
                        user_data.get('skills', []), user_data.get('domain', 'IT'),
                        row['source'], user_data, activity_history, row['posted_at']
                    )
                    cursor.execute("""
                        UPDATE jobs SET 
                            score = ?, 
                            matched_skills = ?, 
                            explanation = ? 
                        WHERE id = ?
                    """, (score, json.dumps(matched_skills), json.dumps(explanations), row['id']))
                    updated_count += 1
                    
                    # 10/10 Reliability: Batch commit to prevent massive transaction lock
                    if (i + 1) % 50 == 0:
                        conn.commit()
                except Exception as loop_err:
                    logger.warning(f"⚠️ Skipping re-scoring for job ID {row['id']}: {str(loop_err)}")
                    continue
            
            conn.commit()
            logger.info(f"💾 Database: Successfully re-scored {updated_count} jobs.")
    except Exception as e:
        logger.error(f"❌ Transaction failure in recalculate_all_scores: {str(e)}")
        raise e

def cleanup_old_jobs(days=30):
    """
    10/10 Scalability: Automatically evicts old discovery data.
    Preserves jobs that are 'Applied', 'Saved', or recently Discovery.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Delete jobs older than X days that aren't 'Saved' or 'Applied'
            cursor.execute("""
                DELETE FROM jobs 
                WHERE discovery_date < datetime('now', '-' || ? || ' days')
                AND id NOT IN (SELECT job_id FROM applications)
                AND id NOT IN (SELECT job_id FROM user_activity WHERE activity_type = 'save')
            """, (days,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"🧹 Database Maintenance: Evicted {deleted} stale discovery records.")
    except Exception as e:
        logger.error(f"❌ Database cleanup failed: {e}")

def mark_as_sent(job_id):
    """Marks a job as alerted to prevent double notifications."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET sent_telegram = 1 WHERE id = ?",(job_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to mark job {job_id} as sent: {e}")

# --- Seen Jobs CRUD ---

def add_seen_link(link):
    """Enforces discovery timestamp refresh on re-discovery (Requirement: UPSERT)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO seen_jobs (link) VALUES (?)
            ON CONFLICT(link) DO UPDATE SET 
                discovery_date = CURRENT_TIMESTAMP
            """, (link,))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to add seen link: {str(e)}")

def get_all_seen_links():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM seen_jobs")
        links = {row['link'] for row in cursor.fetchall()}
        return links

def get_ignored_links():
    """Returns links of jobs marked as 'ignore' (Requirement 3: Adaptive)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT j.link FROM user_activity a JOIN jobs j ON a.job_id = j.id WHERE a.activity_type = 'ignore'")
        return {row['link'] for row in cursor.fetchall()}

def get_jobs_by_links(links):
    """Retrieves full job objects including DB ID for a list of links (Requirement 1 & 4)."""
    if not links: return []
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(links))
        cursor.execute(f"SELECT * FROM jobs WHERE link IN ({placeholders})", list(links))
        rows = cursor.fetchall()
        
        jobs = []
        for row in rows:
            job = dict(row)
            job['matched_skills'] = json.loads(job['matched_skills']) if job['matched_skills'] else []
            job['explanation'] = json.loads(job['explanation']) if job.get('explanation') else []
            jobs.append(job)
        return jobs

# --- Profile CRUD ---

def save_db_profile(profile_data):
    """Saves profile data with UPSERT and transactional safety."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # SQL Bindings Unified (Fix: id + 4 params = 5 values)
            cursor.execute("""
            INSERT INTO user_profile (id, role, location, domain, skills)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                role=excluded.role,
                location=excluded.location,
                domain=excluded.domain,
                skills=excluded.skills
            """, (
                profile_data.get('role'),
                profile_data.get('location'),
                profile_data.get('domain'),
                json.dumps(profile_data.get('skills', []))
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] save_db_profile: {str(e)}")
        raise e

def get_db_profile():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        data['skills'] = json.loads(data['skills'])
        return data
    return None

# --- Applications CRUD ---

def add_application(job_id, status='Applied', notes=''):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO applications (job_id, status, applied_date, notes)
    VALUES (?, ?, ?, ?)
    """, (job_id, status, datetime.now().isoformat(), notes))
    conn.commit()
    conn.close()

def get_applications():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.*, j.title, j.company, j.link 
    FROM applications a 
    JOIN jobs j ON a.job_id = j.id
    ORDER BY a.applied_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- User Activity Telemetry (Adaptive AI Signal) ---

def add_user_activity(job_id, type_):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO user_activity (job_id, activity_type)
    VALUES (?, ?)
    """, (job_id, type_))
    conn.commit()
    conn.close()

def get_activity_history(limit=100):
    """Requirement 1 & 3: Returns recent activity with job context for similarity matching."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.activity_type, j.title, j.company, j.description, j.source, j.matched_skills
    FROM user_activity a
    JOIN jobs j ON a.job_id = j.id
    ORDER BY a.timestamp DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        item = dict(r)
        item['matched_skills'] = json.loads(item['matched_skills']) if item['matched_skills'] else []
        history.append(item)
    return history

def get_ignored_links():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT j.link FROM user_activity a
    JOIN jobs j ON a.job_id = j.id
    WHERE a.activity_type = 'ignore'
    """)
    links = {r['link'] for r in cursor.fetchall()}
    conn.close()
    return links

# --- Settings / Last Run Helpers ---

def save_db_last_run():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) 
    VALUES ('last_run_time', ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (datetime.now().isoformat(),))
    conn.commit()
    conn.close()

def get_db_last_run():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'last_run_time'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"last_run_time": row['value']}
    return None

# Initialize on import
init_db()
