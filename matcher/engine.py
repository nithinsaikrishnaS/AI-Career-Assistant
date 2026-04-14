import re
from collections import Counter
from utils.nlp import normalize_text, MASTER_SKILLS_LIST, get_job_age_days

# --- UNIVERSAL DISCOVERY CONFIGURATION (Requirement: Role Intelligence) ---

DOMAIN_ROLE_MAP = {
    "Mobile Development": ["mobile", "android", "ios", "flutter", "react native", "app", "kotlin", "swift", "native", "dart"],
    "Data & AI": ["data", "ai", "machine learning", "ml", "analytics", "scientist", "deep learning", "nlp", "vision", "aiml", "big data", "spark"],
    "Cybersecurity": ["cyber", "security", "pentest", "infosec", "soc", "firewall", "encryption", "ethical", "hacking"],
    "IT/Software": ["software", "backend", "frontend", "full stack", "web", "java", "python", "javascript", "sde", "coding", "node", "react", "mern", "cloud", "reactjs", "nodejs", "scripting"],
    "Marketing": ["marketing", "seo", "social media", "content", "brand", "digital marketing", "ads", "digital", "adwords"],
    "Finance": ["finance", "accountant", "audit", "banking", "investment", "tax", "fintech", "accounts", "chartered"],
    "HR": ["hr", "human resources", "recruiter", "talent", "payroll", "onboarding", "staffing"],
    "Operations": ["operations", "ops", "supply chain", "logistics", "management", "coordinator", "admin", "office"],
    "Engineering": ["civil", "mechanical", "electrical", "electronics", "structural", "cad", "hardware", "biomedical"],
    "Design": ["design", "ui", "ux", "graphic", "illustrator", "photoshop", "figma", "creative", "artist", "branding"]
}

EXPANSION_MAP = {
    "IT/Software": ["Software Developer", "Backend Engineer", "Frontend Developer", "Full Stack Engineer"],
    "Mobile Development": ["Android Developer", "iOS Developer", "Flutter Developer", "React Native Developer"],
    "Data & AI": ["Machine Learning Engineer", "Data Scientist", "AI Engineer", "Data Analyst"],
    "Marketing": ["Marketing Associate", "SEO Specialist", "Digital Marketing Executive", "Content Strategist"],
    "Finance": ["Financial Analyst", "Accountant", "Investment Analyst", "Tax Associate"],
    "HR": ["HR Coordinator", "Technical Recruiter", "Talent Acquisition Specialist"],
    "Operations": ["Operations Manager", "Supply Chain Coordinator", "Project Coordinator"],
    "Cybersecurity": ["Security Analyst", "Pentester", "Cybersecurity Engineer"],
    "Engineering": ["Civil Engineer", "Mechanical Engineer", "Electrical Engineer"],
    "Design": ["UI/UX Designer", "Product Designer", "Graphic Designer"]
}

NEGATIVE_KEYWORDS = [
    "senior", "lead", "manager", "head of", "principal", "sr.", "architect", 
    "staff", "director", "vp", "expert", "experienced", "technical lead", "specialist"
]

# --- INTELLIGENCE LAYER 1: Normalization & Detection ---

def detect_domain(text, title_context=None):
    """
    Universal Domain Classification Layer (Requirement 5).
    Weights Title keywords higher than Description keywords to avoid 'Greedy' matches.
    """
    if not text: return "general"
    
    # 1. Normalize and score
    tokens = normalize_text(text).split()
    title_tokens = normalize_text(title_context).split() if title_context else []
    
    scores = Counter()
    for domain, keywords in DOMAIN_ROLE_MAP.items():
        for kw in keywords:
            # Title Match (Weight: 5)
            if kw in title_tokens:
                scores[domain] += 5
            # Description/General Match (Weight: 1)
            elif kw in tokens:
                scores[domain] += 1
                
    if not scores: return "general"
    
    # Tie-breaking: Use most common, but filter out zero/low scores
    top_domains = scores.most_common(2)
    if not top_domains: return "general"
    
    return top_domains[0][0]

def expand_role(user_role):
    """Layer 3: Autonomous Role Expansion."""
    if not user_role: return ["software developer", "engineer"]
    
    domain = detect_domain(user_role)
    if domain in EXPANSION_MAP:
        expansions = EXPANSION_MAP[domain].copy()
        # Ensure user's exact input is prioritized
        if user_role not in expansions: expansions.insert(0, user_role)
        return expansions[:4] # Keep top 4 for performance
        
    return ["software developer", "analyst", "engineer", user_role]

# --- ELIGIBILITY GATES (Requirement 1, 2, 3) ---

def check_fresher_eligibility(title, description):
    """
    Strict Fresher-Level Gate. Returns (is_eligible, reason).
    Reject if: numerical exp >= 2 OR title matches seniority keywords.
    Allow: Internship keywords override senior keywords if in title/desc.
    """
    text = f"{title} {description}".lower()
    
    # Whitelist: Internships are always allowed (Requirement 6)
    if "internship" in text or "intern" in text:
        return True, "Internship Whitelisted"

    # 1. Seniority Keyword Rejection (Requirement 3)
    norm_title = title.lower()
    if any(re.search(rf'\b{re.escape(kw)}\b', norm_title) for kw in NEGATIVE_KEYWORDS):
        return False, f"Senior Title Detected: {norm_title}"

    # 2. Numerical Experience Extraction (Requirement 1 & 2)
    # Detect patterns like: 2+ years, 2-5 years, at least 3 years, minimum of 2 years
    exp_patterns = [
        r'(\d+)\+?\s*(?:-|\s*to\s*)?(\d+)?\s*years?',
        r'minimum of\s*(\d+)\s*years?',
        r'at least\s*(\d+)\s*years?',
        r'min\s*(\d+)\s*years?',
    ]
    
    for pattern in exp_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            try:
                # Group 1 is min, Group 2 is max (if exists)
                min_val = int(match.group(1))
                max_val = int(match.group(2)) if match.group(2) else min_val
                
                # Reject if threshold reaches 2 years (Requirement 2)
                if min_val >= 2 or max_val >= 2:
                    return False, f"Hard Experience Gate: Requires {min_val}-{max_val} years"
            except (ValueError, IndexError):
                continue
    
    # 3. Contextual Seniority (Requirement 3)
    # Catch cases like "experience in leading a team" or "5 years of experience" hidden in text
    if any(re.search(rf'\b{re.escape(kw)}\b', text) for kw in ["5 years", "10 years", "8 years", "expert in"]):
        return False, "High Experience Keywords Detected"

    return True, "Fresher Eligible"

# --- UTILS ---

def is_job_fresh(date_str):
    age = get_job_age_days(date_str)
    if age == 999: return True
    return age <= 7

# normalize locally deprecated for centralized normalize_text

def expand_aliases(text):
    # Reduced to core aliases for Universal Role Intelligence
    alias_map = {
        "ml": "machine learning", "ai": "artificial intelligence", "js": "javascript",
        "sde": "software engineer", "swe": "software engineer", "aiml": "ai machine learning"
    }
    expanded = text
    for short, full in alias_map.items():
        if re.search(rf'\b{re.escape(short)}\b', text, re.IGNORECASE):
            expanded += f" {full}"
    return expanded

def classify_domain(text):
    """Job Domain Classification Layer (Requirement 5)."""
    return detect_domain(text)

# --- ADAPTIVE AI formulæ (Requirement 4 & 5) ---

# --- ASSISTIVE INTELLIGENCE (Requirement 6 & 7) ---

def calculate_skill_gap(desc_text, user_skills):
    """Identifies highly relevant skills in the job that the user lacks."""
    desc_norm = normalize_text(desc_text)
    user_skills_norm = {normalize_text(s) for s in user_skills}
    
    # Identify skills from master list found in job but not in user profile
    gaps = []
    # Only pick from master skills to avoid noise
    for skill in MASTER_SKILLS_LIST:
        if len(gaps) >= 3: break
        if skill in desc_norm and skill not in user_skills_norm:
            gaps.append(skill.upper())
    return gaps

# --- BEHAVIORAL INTELLIGENCE ---

def calculate_adaptive_boost(words_in_job, activity_history):
    """Calculates boost/penalty based on recent behavior (Requirement 2 & 4)."""
    if not activity_history: return 0, []
    
    behavior_boost = 0
    adaptive_explanations = []
    
    # 1. Clustering Interests (Applied/Saved)
    interested_keywords = []
    ignored_keywords = []
    for act in activity_history[:20]:
        # Extract keywords from title/desc of historical jobs
        words = set(normalize_text(act.get('title', '') + " " + act.get('description', '')).split())
        if act['activity_type'] in ['apply', 'save', 'view']:
            interested_keywords.extend(list(words))
        elif act['activity_type'] == 'ignore':
            ignored_keywords.extend(list(words))

    # Calculate overlap
    pos_overlap = len(words_in_job.intersection(set(interested_keywords)))
    if pos_overlap > 10:
        behavior_boost += 12
        adaptive_explanations.append("AI: Matches your recent interest patterns")
    
    # Calculate conflict with ignored clusters
    neg_overlap = len(words_in_job.intersection(set(ignored_keywords)))
    if neg_overlap > 8:
        behavior_boost -= 25
        adaptive_explanations.append("AI: Features patterns you recently dismissed")

    return behavior_boost, adaptive_explanations

# --- CORE MATCHING ENGINE ---
def calculate_match(job_title, job_description, job_location, user_skills, stream, 
                    job_source="aggregator", preferences=None, activity_history=None, posted_at="Today"):
    """
    Universal Intelligence Engine (Requirement 6).
    """
    norm_title = normalize_text(job_title)
    norm_desc = normalize_text(job_description)
    expanded_job_text = expand_aliases(f"{norm_title} {norm_desc}")
    
    score = 0
    matched_skills = []
    explanations = []
    
    # 1. Domain Detection & Match (Requirement 6A)
    pref_role = preferences.get('role', "").lower() if preferences else ""
    user_domain = detect_domain(pref_role, title_context=pref_role) if pref_role else "general"
    job_domain = detect_domain(f"{job_title} {job_description}", title_context=job_title)
    
    if user_domain != "general" and job_domain != "general":
        if user_domain == job_domain:
            score += 30
            explanations.append(f"✅ Domain Match: Role aligns with your focus in {job_domain}")
        else:
            score -= 20
            explanations.append(f"⚠️ Domain Mismatch: This is a {job_domain} role")

    # 2. Expanded Role Match (Requirement 6B)
    expanded_pref_roles = [normalize_text(r) for r in expand_role(pref_role)]
    role_hit = False
    for r in expanded_pref_roles:
        if r in expanded_job_text:
            role_hit = True; break
    
    if role_hit:
        score += 25
        explanations.append("✅ Role Alignment: Matches your target role criteria")
    
    # 3. Skill Matching (Requirement 6C)
    for skill in user_skills:
        skill_norm = normalize_text(skill)
        if skill_norm in expanded_job_text:
            score += 10
            matched_skills.append(skill)
    
    # 4. Freshness (Requirement 6D)
    age = get_job_age_days(posted_at)
    if age <= 7:
        score += 10
        explanations.append("✅ Fresh Opportunity: Posted in the last week")

    # 5. Seniority Filter / Hardness Penalty (Requirement 6E)
    is_senior, reason = check_fresher_eligibility(job_title, job_description)
    if not is_senior:
        score -= 50
        explanations.append(f"❌ Seniority Risk: {reason}")

    # Fallback Guarantee: Ensure minimum scoring for vague matches
    if score < 0: score = 0
    final_score = int(min(score, 100))

    return final_score, matched_skills, explanations, {
        "skill_gap": [],
        "domain": job_domain
    }

def verify_job_quality(job, matched_skills):
    """Basic sanity check to prevent garbage data."""
    title = job.get('title', '')
    desc = job.get('description', '')
    link = job.get('link', '')
    if not title or len(title) < 5: return False, "Invalid Title"
    if not link or "http" not in link: return False, "Invalid Link"
    if not desc or len(desc) < 50: return False, "Hollow Description"
    return True, "Success"
