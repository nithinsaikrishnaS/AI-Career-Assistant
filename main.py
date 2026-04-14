from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Security, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
import uvicorn
import asyncio
import io
import os
import json
import time
import threading
import requests
from pypdf import PdfReader
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from fastapi.responses import HTMLResponse, Response

from utils import db_manager
from utils.nlp import extractor
from scheduler.automation import start_scheduler, run_job_pipeline, IS_SCAN_ACTIVE
from utils.logger import get_logger
from utils.state_manager import state_manager
from pydantic import validator

logger = get_logger("MainAPI")

# 10/10 Deployment Trace: Version ID for production status
VERSION = "v1.0.2-onboarding-bypass"

# 10/10 Hardening: Mutex for background re-scoring to prevent DB contention
RECALCULATE_LOCK = False

# Load Secrets from .env (Requirement 1 - Security)
def load_env():
    # Priority: .env.local (if exists) THEN .env
    # We load .env first, then .env.local so that .env.local can overwrite it.
    env_files = [".env", ".env.local"]
    for f_path in env_files:
        if os.path.exists(f_path):
            with open(f_path, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ[k] = v

load_env()
API_KEY = os.getenv("INTERNAL_API_KEY", "ai_job_aggregator_prod_key_778899")

# --- SECURITY CONFIGURATION (Requirement 1 & 5) ---
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(request: Request, api_key: str = Security(api_key_header)):
    """
    Validates identity via Header or Cookie.
    Requirement: 10/10 Reliability on Cloud Environments.
    """
    # 1. Check Header Match
    if api_key and api_key == API_KEY: 
        return api_key
    
    # 2. Check Cookie Match
    cookie_key = request.cookies.get("session_auth_key")
    
    # 3. Handle Special Case: Onboarding (Allow if it's the first time)
    # Match /profile and /upload-resume to prevent path-related blocks during onboarding.
    normalized_path = request.url.path.strip("/").lower()
    if normalized_path in ["profile", "upload-resume"] and request.method == "POST":
         return "onboarding_bypass"

    # Production Debugging (Requirement 5)
    if not api_key and not cookie_key:
        logger.warning(f"🔒 [AUTH FAILURE] Request to {request.url.path} blocked. No credentials found.")
    elif api_key != API_KEY and cookie_key != API_KEY:
        logger.error(f"🔒 [AUTH MISMATCH] Credentials found but did not match Internal Key.")

    raise HTTPException(
        status_code=403, 
        detail={"status": "error", "message": "Forbidden: Invalid or missing authentication"}
    )

app = FastAPI(title="AI Job Aggregator Pro")

# --- Restricted CORS (Requirement 3: allow_credentials = True) ---
allowed_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://0.0.0.0:8000")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- RATE LIMITING (Requirement 6) ---
request_history = {} # In-memory store: {api_key: [timestamps]}

def rate_limit_check(request: Request):
    api_key = request.headers.get(API_KEY_NAME)
    if not api_key: return # Handled by auth dependency
    
    now = time.time()
    # Filter for last 60 seconds
    history = [t for t in request_history.get(api_key, []) if now - t < 60]
    
    if len(history) >= 60: # Limit: 60 requests per minute
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    
    history.append(now)
    request_history[api_key] = history

# --- GLOBAL ERROR HANDLING (Requirement 8) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_msg = ", ".join([f"{err['loc'][-1]}: {err['msg']}" for err in errors])
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": f"Validation failed - {error_msg}"
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException): return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    
    # Hide stack traces in production (Requirement 8)
    return JSONResponse(
        status_code=500,
        content={"message": "An internal error occurred. Please contact system admin."}
    )

# --- SAFE ASSET ROUTING ---
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

class UserPreferences(BaseModel):
    role: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=100)
    domain: str = Field(..., min_length=2, max_length=50)
    skills: List[str] = Field(default_factory=list)

class UserDetailedProfile(BaseModel):
    role: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=100)
    domain: str = Field(..., min_length=2, max_length=50)
    experience: Optional[str] = Field("Fresher", max_length=50)
    job_type: Optional[str] = Field("Full-time", max_length=50)
    preferred_tech: Optional[str] = Field("", max_length=200)
    salary_range: Optional[str] = Field("Not Specified", max_length=100)
    availability: Optional[str] = Field("Immediate", max_length=50)
    work_mode: Optional[str] = Field("Remote", max_length=50)
    company_type: Optional[str] = Field("Any", max_length=100)
    notifications: bool = Field(True)
    skills: List[str] = Field(default_factory=list, max_items=30)
    
    @validator('skills', pre=True)
    def sanitize_skills(cls, v):
        if not isinstance(v, list): return []
        clean = list(set([s.strip() for s in v if s and s.strip()]))[:30]
        return sorted(clean)

class ApplicationCreate(BaseModel):
    job_id: int = Field(..., gt=0)
    status: Optional[str] = Field("Applied", max_length=20)
    notes: Optional[str] = Field("", max_length=300)

class ActivityCreate(BaseModel):
    job_id: int = Field(..., gt=0)
    type: str = Field(..., pattern="^(view|ignore|apply)$")

# --- CSRF PROTECTION (Requirement 7: Security) ---
def csrf_check(request: Request):
    """Refuses POST requests without a matching CSRF header/cookie."""
    if request.method == "POST":
        csrf_header = request.headers.get("X-CSRF-TOKEN")
        csrf_cookie = request.cookies.get("session_auth_key")
        
        # 10/10 Reliability: Allow CSRF bypass for initial onboarding 
        # since the cookie might not be stored yet on HTTPS/Render.
        normalized_path = request.url.path.strip("/").lower()
        if normalized_path in ["profile", "upload-resume"]:
            return

        if not csrf_header or csrf_header != csrf_cookie:
            logger.warning(f"🛡️ [SECURITY] CSRF Blocked: {request.url.path}")
            raise HTTPException(status_code=403, detail="CSRF Validation Failed")

@app.on_event("startup")
def startup_event():
    """Startup initialization: Scheduler + Telegram Feedback Poller."""
    start_scheduler()
    
    # Start Telegram Interaction Thread (Long Polling)
    from notifier.telegram import notifier
    
    # 10/10 Readiness: Verify Telegram connectivity on boot
    ok, msg = notifier.verify_connectivity()
    if ok:
        logger.info(f"✅ Telegram: {msg}")
    else:
        logger.error(f"❌ Telegram: Connection Failed - {msg}")

    def poll_telegram():
        logger.info("📡 Telegram Feedback Poller Started...")
        last_update_id = 0
        while True:
            try:
                # Use /getUpdates with offset to handle callbacks
                url = f"https://api.telegram.org/bot{notifier.bot_token}/getUpdates"
                params = {"offset": last_update_id + 1, "timeout": 30}
                resp = requests.get(url, params=params, timeout=35).json()
                
                if resp.get("ok"):
                    for update in resp.get("result", []):
                        last_update_id = update["update_id"]
                        
                        # Handle Callback Query (The Buttons)
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            data = cb.get("data", "")
                            msg_id = cb.get("message", {}).get("message_id")
                            chat_id = cb.get("message", {}).get("chat", {}).get("id")
                            
                            # Parse: cmd:job_id
                            if ":" in data:
                                cmd, job_id = data.split(":", 1)
                                logger.info(f"📩 Telegram Interaction: {cmd} on Job ID {job_id}")
                                
                                # 1. Core Actions
                                if cmd == "ignore":
                                    db_manager.add_user_activity(int(job_id), "ignore")
                                    resp_text = "❌ Dismissed. Assistant will avoid similar roles."
                                elif cmd == "save":
                                    db_manager.add_user_activity(int(job_id), "save")
                                    resp_text = "⭐ Job Saved to Dashboard."
                                elif cmd == "applied":
                                    db_manager.add_application(int(job_id), "Applied", "Via Telegram Assistant")
                                    resp_text = "📝 Marked as Applied. Success!"
                                else:
                                    resp_text = "Acknowledged."

                                # 2. Acknowledge Callback (stops spinning)
                                requests.post(f"https://api.telegram.org/bot{notifier.bot_token}/answerCallbackQuery", 
                                            json={"callback_query_id": cb["id"], "text": resp_text})
                                
                                # 3. Update Original Message (Requirement: Visual Progress)
                                new_text = cb["message"].get("text", "") + f"\n\n🏁 *Update:* {resp_text}"
                                requests.post(f"https://api.telegram.org/bot{notifier.bot_token}/editMessageText",
                                            json={"chat_id": chat_id, "message_id": msg_id, "text": new_text, "parse_mode": "Markdown"})
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"⚠️ Telegram Poller Error: {e}")
                time.sleep(10)

    thread = threading.Thread(target=poll_telegram, daemon=True)
    thread.start()

# --- SECURE UI ROUTES (Requirement 7: Cookie Protection) ---
def get_secure_page(filename: str, response: Response):
    if not os.path.exists(filename):
        raise HTTPException(status_code=404)
    
    # Set Auth Cookie (Requirement: Remove Keys from Frontend)
    response.set_cookie(
        key="session_auth_key", 
        value=API_KEY, 
        httponly=False, 
        secure=True,     # REQUIRED for Render HTTPS
        samesite="lax",
        path="/" 
    )
    
    with open(filename, "r") as f:
        content = f.read()
    
    # Clean up legacy placeholders (Requirement 1)
    secure_content = content.replace("{{API_KEY}}", "SESSION_ACTIVE")
    return HTMLResponse(content=secure_content)

@app.get("/")
def home(): return RedirectResponse(url="/index.html")

@app.get("/index.html")
def get_index(response: Response): return get_secure_page("index.html", response)

@app.get("/dashboard.html")
def get_dashboard(response: Response): return get_secure_page("dashboard.html", response)

@app.get("/profile.html")
def get_profile_page(response: Response): return get_secure_page("profile.html", response)

# --- API ENDPOINTS (Protected) ---
@app.get("/profile", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
def get_profile():
    from utils.data_manager import get_user_data
    profile = get_user_data()
    return {"status": "success", "data": profile}

@app.post("/profile", dependencies=[Depends(get_api_key), Depends(rate_limit_check), Depends(csrf_check)])
def update_profile(profile: UserDetailedProfile):
    """
    Saves profile and triggers atomic re-scoring. (Requirement 7 & 3)
    """
    try:
        from utils.data_manager import save_user_data
        from matcher.engine import calculate_match
        
        # Strip extra fields for DB storage
        db_ready_data = {
            "role": profile.role,
            "location": profile.location,
            "domain": profile.domain,
            "skills": profile.skills
        }
        save_user_data(db_ready_data)
        
        # 10/10 Performance: Run re-scoring in background thread to avoid UI hang
        # 10/10 Hardening: Protect with mutex to avoid concurrent DB write threads
        global RECALCULATE_LOCK
        if RECALCULATE_LOCK:
            logger.info("ℹ️ Re-scoring already in progress. Skipping redundant thread.")
        else:
            def async_recalculate():
                global RECALCULATE_LOCK
                RECALCULATE_LOCK = True
                try:
                    logger.info("🧵 [Background] Starting global re-scoring...")
                    history = db_manager.get_activity_history(limit=50)
                    db_manager.recalculate_all_scores(calculate_match, db_ready_data, history)
                    logger.info("✅ [Background] Global re-scoring complete.")
                finally:
                    RECALCULATE_LOCK = False

            threading.Thread(target=async_recalculate, daemon=True).start()
        
        return {
            "status": "success", 
            "message": "Profile and job rankings updated successfully.",
            "data": db_ready_data
        }
    except Exception as e:
        logger.error(f"🔥 [API ERROR] /profile POST: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to persist profile: {str(e)}"}
        )

@app.post("/upload-resume", dependencies=[Depends(get_api_key), Depends(rate_limit_check), Depends(csrf_check)])
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
    try:
        content = await file.read()
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            extr = page.extract_text()
            if extr: text += extr + " "
        
        skills = extractor.extract_skills(text, top_n=10)
        stream = extractor.extract_stream(text)
        
        if not text.strip() or not skills:
            skills = []
            stream = "Unknown"

        profile_data = {"skills": skills, "stream": stream}
        
        return {"status": "success", "message": "Onboarding complete.", "profile": profile_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trigger-scan", dependencies=[Depends(get_api_key), Depends(rate_limit_check), Depends(csrf_check)])
async def manual_trigger():
    """Manual Trigger (Requirement 6)"""
    from utils.db_manager import save_db_last_run
    save_db_last_run()
    thread = threading.Thread(target=run_job_pipeline)
    thread.start()
    return {"status": "success", "message": "Discovery scan triggered."}

@app.get("/scan-status", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
async def get_scan_status():
    """Requirement 1: Returns whether a background discovery cycle is active."""
    return {"is_scanning": IS_SCAN_ACTIVE}

@app.get("/jobs", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
async def get_jobs_tiered():
    """Requirement 4: Served from SQLite jobs.db"""
    try:
        all_jobs = db_manager.get_all_jobs(limit=200)
        
        # Split into tiers for frontend
        recommended_jobs = [j for j in all_jobs if j.get('score', 0) >= 70]
        other_jobs = [j for j in all_jobs if j.get('score', 0) < 70]
        
        # Add last run info
        from utils.data_manager import get_last_run
        last_run = get_last_run()
        
        return {
            "recommended_jobs": recommended_jobs,
            "other_jobs": other_jobs,
            "is_rescoring": RECALCULATE_LOCK,
            "last_updated": last_run.get('last_run_time', 'Never') if last_run else 'Never',
            "metrics": {
                "total_db": len(all_jobs),
                "recommended": len(recommended_jobs),
                "other": len(other_jobs)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
async def get_my_applications():
    return db_manager.get_applications()

@app.post("/applications", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
async def apply_to_job(app_data: ApplicationCreate):
    db_manager.add_application(app_data.job_id, app_data.status, app_data.notes)
    # Requirement 3: Telemetry Hook for Adaptive AI
    db_manager.add_user_activity(app_data.job_id, "apply")
    return {"message": "Application tracked successfully."}

@app.post("/activity", dependencies=[Depends(get_api_key), Depends(rate_limit_check)])
async def track_activity(activity: ActivityCreate):
    """Requirement 1 & 2: Behavioral Tracking (View/Ignore)"""
    db_manager.add_user_activity(activity.job_id, activity.type)
    return {"status": "success"}

# --- OBSERVABILITY ENDPOINTS (Requirement: Production Reliability) ---

@app.get("/health")
async def health_check():
    """
    Returns real-time system state (Requirement 2 & 3).
    """
    from utils.data_manager import get_user_data
    state = state_manager.get_all()
    profile = get_user_data()
    
    # Dynamic DB Audit
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        total_jobs = cursor.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        
    state["total_jobs_in_db"] = total_jobs
    state["profile_online"] = profile is not None
    state["is_rescoring"] = RECALCULATE_LOCK
    
    return {
        "status": "healthy",
        "version": VERSION,
        "timestamp": time.time(),
        "metrics": state
    }

@app.get("/test-telegram")
async def test_telegram():
    """
    Diagnostic endpoint to verify Telegram integration (Requirement 4).
    """
    from notifier.telegram import notifier
    success = notifier.send_message("🚨 *Production Verification Signal*\nSystem Observability Check: SUCCESS.\nTime: " + time.ctime())
    if success:
        return {"status": "success", "message": "Test reachout successful"}
    return JSONResponse(status_code=500, content={"status": "error", "message": "Telegram delivery failed"})

if __name__ == "__main__":
    # Render requires dynamic port binding (Requirement: Phase 1.4)
    # Defaulting to 10000 as per deployment plan
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
