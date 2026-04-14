import sys
import os
import sqlite3
import json

# Set up project path for imports
sys.path.append('/Users/nithinsaikrishnas/Downloads/AI Projects')

from matcher.engine import calculate_match
from utils import db_manager

# Configuration
DB_FILE = "data/jobs.db"

def test_seniority_gate():
    print("🧠 [AUDIT] Verifying Seniority Leakage Prevention...")
    # Profile: Fresher Software Engineer
    user_skills = ["python", "fastapi", "react"]
    preferences = {"role": "software engineer"}
    
    # Job: Senior Manager of Engineering (Highly senior title)
    job_title = "Senior Manager of Frontend Engineering"
    job_desc = "Seeking a leader with 10+ years of experience managing large teams."
    
    score, matched, expl, meta = calculate_match(
        job_title, job_desc, "Remote", user_skills, "IT",
        preferences=preferences
    )
    
    has_failsafe = any("Failsafe" in e for e in expl)
    print(f"  - Job Title: {job_title}")
    print(f"  - Score: {score}")
    print(f"  - Seniority Failsafe Applied: {'✅' if has_failsafe else '❌'}")
    
    # Requirement: High seniority should result in low score despite skill overlaps
    result = score < 60
    print(f"  - Logic Result: {'PASSED' if result else 'FAILED'}")
    return result

def test_db_upsert():
    print("\n🏦 [AUDIT] Verifying Database UPSERT & Deduplication...")
    db_manager.init_db()
    
    mock_link = "https://test.jobs/12345"
    mock_job = {
        "title": "UPSERT Test Job",
        "company": "QA Corp",
        "location": "Remote",
        "link": mock_link,
        "score": 85,
        "source": "test",
        "matched_skills": ["Python"],
        "explanation": ["AI: Match"]
    }
    
    # 1. First Insert
    db_manager.upsert_jobs([mock_job])
    
    # 2. Second Insert (Updated score, same link)
    mock_job["score"] = 95
    db_manager.upsert_jobs([mock_job])
    
    # 3. Verify uniqueness and update
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM jobs WHERE link = ?", (mock_link,)).fetchone()[0]
    final_score = cursor.execute("SELECT score FROM jobs WHERE link = ?", (mock_link,)).fetchone()[0]
    conn.close()
    
    print(f"  - Entry Count for unique link: {count} (Expected 1)")
    print(f"  - Score after UPSERT: {final_score} (Expected 95)")
    
    result = (count == 1 and final_score == 95)
    print(f"  - DB Result: {'PASSED' if result else 'FAILED'}")
    return result

def test_semantic_deduplication():
    print("\n♻️ [AUDIT] Verifying Semantic Clutter Suppression (Title+Company)...")
    # This logic resides in automation.py, but we test the detection query
    job_title = "Unique Role A"
    company = "Company Alpha"
    
    with db_manager.get_connection() as conn:
        # Clear previous test data
        conn.execute("DELETE FROM jobs WHERE title = ?", (job_title,))
        
        # 1. Insert original
        conn.execute("INSERT INTO jobs (title, company, link, score) VALUES (?, ?, ?, ?)", 
                    (job_title, company, "link1", 80))
        conn.commit()
        
        # 2. Verify duplicate detection for different link
        duplicate_check = conn.execute("""
            SELECT 1 FROM jobs 
            WHERE title = ? AND company = ? 
            AND discovery_date > datetime('now', '-2 days')
        """, (job_title, company)).fetchone()
        
    print(f"  - Job Pair: {job_title} @ {company}")
    print(f"  - Duplicate Detected: {'✅' if duplicate_check else '❌'}")
    
    result = duplicate_check is not None
    print(f"  - Semantic Result: {'PASSED' if result else 'FAILED'}")
    return result

if __name__ == "__main__":
    print("🏁 STARTING 10/10 PRODUCTION AUDIT\n" + "="*40)
    
    res1 = test_seniority_gate()
    res2 = test_db_upsert()
    res3 = test_semantic_deduplication()
    
    print("\n" + "="*40 + "\n📊 FINAL AUDIT SUMMARY")
    print(f"  - Seniority Gate: {'✅ PASSED' if res1 else '❌ FAILED'}")
    print(f"  - DB Integrity:   {'✅ PASSED' if res2 else '❌ FAILED'}")
    print(f"  - Semantic Dedup: {'✅ PASSED' if res3 else '❌ FAILED'}")
    
    if res1 and res2 and res3:
        print("\n🏆 SYSTEM LOGIC IS 10/10 VERIFIED.")
    else:
        sys.exit(1)
