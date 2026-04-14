import re
import os
import json
from datetime import datetime, timedelta
from collections import Counter

# Optional AI/NLP dependencies with safe fallbacks to prevent startup hangs
# We lazy-load these inside functions to avoid Python 3.9 / SSL startup crashes
spacy = None
nlp = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Master Configuration Constants
MASTER_SKILLS_LIST = [
    "python", "javascript", "react", "node", "java", "sql", "aws", "docker", 
    "machine learning", "api", "rest", "graphql", "css", "html", "mongodb",
    "postgresql", "git", "linux", "flask", "django", "fastapi", "pandas",
    "numpy", "scikit-learn", "tensorflow", "pytorch", "c++", "c#", "php",
    "mern stack", "frontend", "backend", "full stack", "devops", "cloud computing"
]

SKILL_NORMALIZATION_MAP = {
    "ml": "machine learning", "ai": "machine learning", "js": "javascript",
    "node.js": "node", "nodejs": "node", "react.js": "react", "reactjs": "react",
    "amazon web services": "aws", "fullstack": "full stack", "mern": "mern stack",
    "rest api": "api", "mongodb": "mongodb", "mongo": "mongodb"
}

def get_nlp():
    """Lazy-loader for spaCy. Only attempts to load if strictly necessary."""
    global nlp, spacy
    if nlp is not None: return nlp
    try:
        if spacy is None:
            import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        # If any error occurs (import, model load, or attribute error), we fall back gracefully
        nlp = None
    return nlp

def normalize_text(text):
    if not text: return ""
    text = text.lower()
    return re.sub(r'[^a-z0-9\s]', '', text)

def get_job_age_days(date_str):
    """
    Normalizes diverse date strings into age in days.
    Supports: '3 days ago', 'Yesterday', 'Today', '2024-03-10', etc.
    Returns: integer age in days, 999 if unknown.
    """
    if not date_str or date_str.lower() == "unknown date":
        return 999
        
    date_str = date_str.lower().strip()
    
    # 1. Handle Relative Phrases
    if any(re.search(rf'\b{x}\b', date_str) for x in ["just now", "today", "0 days ago"]):
        return 0
    if "yesterday" in date_str or re.search(r'\b1 day ago\b', date_str):
        return 1
        
    day_match = re.search(r'(\d+)\s*days?\s*ago', date_str)
    if day_match:
        return int(day_match.group(1))
        
    # 2. Handle Absolute Formats (Simplified)
    try:
        # Check for YYYY-MM-DD or DD-MM-YYYY or Mon DD, YYYY
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%b %d, %Y", "%B %d, %Y", "%B %d %Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return (datetime.now() - dt).days
            except:
                continue
    except:
        pass
        
    return 999

class SkillExtractor:
    def __init__(self):
        # Pre-compile regex for ultra-fast matching without heavy NLP models
        self.patterns = []
        for skill in MASTER_SKILLS_LIST:
            self.patterns.append((skill, re.compile(rf'\b{re.escape(skill)}\b', re.IGNORECASE)))
        
        for variation, canonical in SKILL_NORMALIZATION_MAP.items():
            self.patterns.append((canonical, re.compile(rf'\b{re.escape(variation)}\b', re.IGNORECASE)))

    def extract_skills(self, text, top_n=10):
        if not text: return []
        found = []
        for canonical, pattern in self.patterns:
            if pattern.search(text):
                found.append(canonical)
        
        counts = Counter(found)
        return [sk for sk, c in counts.most_common(top_n)]

    def extract_stream(self, text):
        if not text: return "Other"
        text_lower = text.lower()
        # Production-Ready Stream Mapping (Point 1)
        mappings = {
            "IT": ["computer science", "cse", "information technology", "it", "software", "development", "bca", "mca"],
            "ECE": ["electronics", "ece", "telecommunication", "embedded", "vlsi", "electrical"],
            "Mechanical": ["mechanical", "mech", "manufacturing", "cad", "automobile"],
            "Civil": ["civil", "construction", "site engineer", "structural"]
        }
        for stream, keywords in mappings.items():
            for kw in keywords:
                if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                    return stream
        return "Other"

class JobSummarizer:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-flash-latest')
            except: self.model = None
        else: self.model = None

    def summarize(self, description):
        """AI-powered summary with lightning-fast regex fallback."""
        if not description or len(description) < 50:
            return {"summary": description or "No details.", "key_skills": [], "experience": "Fresher"}
            
        if self.model:
            try:
                prompt = (
                    "Summarize this job in a professional 2-3 line summary. "
                    "Extract experience and key skills. Return ONLY JSON: "
                    '{"summary": "...", "key_skills": ["..."], "experience": "..."}\n\n'
                    f"Description: {description[:3000]}"
                )
                response = self.model.generate_content(prompt)
                text = response.text
                if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
                return json.loads(text)
            except: pass

        # --- FAST FALLBACK (Section 14) ---
        exp_match = re.search(r'(\d+[-/]\d+|\d+)\s*(?:\+)?\s*years?', description.lower())
        experience = exp_match.group(0) if exp_match else "Fresher"
        
        # Smarter fallback: take first two sentences or first 160 chars
        clean_desc = re.sub(r'\s+', ' ', description).strip()
        sentences = re.split(r'(?<=[.!?])\s+', clean_desc)
        summary = " ".join(sentences[:2]) if len(sentences) > 1 else clean_desc[:160] + "..."
        
        return {
            "summary": summary,
            "key_skills": extractor.extract_skills(description, top_n=5),
            "experience": experience
        }

# Singleton instances initialized instantly with zero dependencies
extractor = SkillExtractor()
summarizer = JobSummarizer()
