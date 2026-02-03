import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ai_engine.screener import calculate_resume_score

print("--- Testing AI Scoring Engine ---")
resume_text = "I am a Senior Software Engineer with 5 years of experience in Python, Django, and Machine Learning. I have used PostgreSQL and Docker."
job_desc = "We are hiring a Backend Engineer to build scalable APIs using Python and Django. Experience with SQL databases and containerization is required."
skills = ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes"]

print(f"Resume: {resume_text[:50]}...")
print(f"Job: {job_desc[:50]}...")
print(f"Required Skills: {skills}")

try:
    score = calculate_resume_score(resume_text, job_desc, skills)
    print("\n--- Results ---")
    print(f"Final Match Score: {score['final_score']}%")
    print(f"Semantic Score: {score['semantic_score']}%")
    print(f"Skill Score: {score['skill_score']}%")
    print(f"Matched Skills: {score['matched_skills']}")
    print(f"Missing Skills: {score['missing_skills']}")
    print(f"Classification: {score['classification']}")
    
    if score['final_score'] > 50:
        print("\nSUCCESS: Scoring seems reasonable!")
    else:
        print("\nWARNING: Score seems low for a good match.")
except Exception as e:
    print(f"\nERROR: {e}")
