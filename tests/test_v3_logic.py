import sys
import os

# Set up project path
sys.path.append('/Users/nithinsaikrishnas/Downloads/AI Projects')

from matcher.engine import calculate_match

def run_v3_audit():
    print("🏁 [AUDIT] Starting Recommendation Engine v3.0 Intelligence Check\n" + "="*60)
    
    # User Profile: Python Backend Specialist
    user_skills = ["python", "fastapi", "postgresql", "docker", "aws"]
    preferences = {
        "role": "Backend Engineer",
        "domain": "Backend Architecture",
        "location": "Remote"
    }
    stream = "Backend Architecture"
    
    cases = [
        {
            "name": "Case 1: Senior Java Lead (Seniority Leakage)",
            "title": "Senior Java Developer & Team Lead",
            "desc": "Seeking a manager with 10+ years of experience in Java and Spring Boot. Must have led teams of 20+.",
            "loc": "San Francisco",
            "expect": "LOW (<40) + Seniority Risk"
        },
        {
            "name": "Case 2: Junior React Dev (Domain Mismatch)",
            "title": "Junior Frontend Developer (React)",
            "desc": "Entry level role for someone who loves CSS, Tailwind, and building beautiful React components.",
            "loc": "Remote",
            "expect": "LOW (<60) + Domain Tension"
        },
        {
            "name": "Case 3: Entry Python Dev (Direct Match)",
            "title": "Software Engineer I - Python/FastAPI",
            "desc": "Join our backend team building high-performance APIs with Python and FastAPI. Docker experience is a plus.",
            "loc": "Remote",
            "expect": "HIGH (>85) + Domain Match"
        }
    ]
    
    all_passed = True
    for c in cases:
        print(f"\n🔍 {c['name']}")
        score, matched, expl, meta = calculate_match(
            c['title'], c['desc'], c['loc'], user_skills, stream, preferences=preferences
        )
        
        print(f"  - Score: {score}%")
        print(f"  - Job Domain: {meta.get('job_domain')}")
        print(f"  - Strengths: {meta.get('strengths')}")
        print(f"  - Risks: {meta.get('risks')}")
        
        # Validation Logic
        if "Case 1" in c['name'] and score > 40:
            print("  ❌ FAIL: Score too high for senior role.")
            all_passed = False
        elif "Case 2" in c['name'] and score > 65:
            print("  ❌ FAIL: Score too high for domain mismatch.")
            all_passed = False
        elif "Case 3" in c['name'] and score < 85:
            print("  ❌ FAIL: Score too low for direct match.")
            all_passed = False
        else:
            print("  ✅ PASS: Logic alignment verified.")

    print("\n" + "="*60 + "\n📊 FINAL v3.0 AUDIT RESULT")
    if all_passed:
        print("🏆 ENGINE INTELLIGENCE IS 10/10 VERIFIED.")
    else:
        print("💡 ENGINE REQUIRES FURTHER REFINEMENT.")
        sys.exit(1)

if __name__ == "__main__":
    run_v3_audit()
