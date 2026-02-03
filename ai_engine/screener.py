import spacy
from typing import List, Set, Tuple
import numpy as np

# Global cache for heavy models
_nlp = None
_model = None
_use_fallback = False

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback if model not found, though it should be downloaded
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            _nlp = spacy.load("en_core_web_sm")
    return _nlp

def get_model():
    global _model, _use_fallback
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer, util
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            _use_fallback = False
            print("AI Engine: Loaded Sentence Transformers successfully.")
        except Exception as e:
            print(f"AI Engine: Failed to load Sentence Transformers ({e}). Switching to TF-IDF fallback.")
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            _model = TfidfVectorizer(stop_words='english')
            _use_fallback = True
    return _model

def extract_keywords(text):
    """
    Extracts potential keywords (NOUN, PROPN) from text using spaCy.
    """
    nlp = get_nlp()
    doc = nlp(text)
    keywords = set()
    for token in doc:
        if token.pos_ in ['NOUN', 'PROPN'] and not token.is_stop and token.is_alpha:
            keywords.add(token.lemma_.lower())
    return list(keywords)

def calculate_semantic_similarity(text1, text2):
    """
    Calculates cosine similarity between two texts using sentence embeddings OR TF-IDF fallback.
    """
    model = get_model()
    
    if _use_fallback:
        # TF-IDF approach
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            tfidf_matrix = model.fit_transform([text1, text2])
            score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(score) * 100
        except Exception as e:
            print(f"TF-IDF Error: {e}")
            return 0.0
    else:
        # Sentence Transformers approach
        from sentence_transformers import util
        embeddings = model.encode([text1, text2])
        score = util.cos_sim(embeddings[0], embeddings[1])
        return float(score.item()) * 100

def check_missing_skills(resume_text, required_skills):
    """
    Checks which required skills are present in the resume text.
    Naive, case-insensitive string matching.
    """
    if isinstance(required_skills, str):
        # Handle if comma-separated string passed
        required_skills = [s.strip() for s in required_skills.split(',') if s.strip()]
        
    resume_lower = resume_text.lower()
    missing = []
    matched = []
    
    for skill in required_skills:
        skill_lower = skill.lower()
        # Ensure we match whole words logic could be better, but simple substring for now
        # Ideally use regex for boundaries: r'\b' + re.escape(skill_lower) + r'\b'
        if skill_lower in resume_lower:
            matched.append(skill)
        else:
            missing.append(skill)
            
    return matched, missing

def calculate_resume_score(resume_text, job_description, required_skills, weights={'semantic': 0.6, 'skills': 0.4}):
    """
    Aggregates semantic score and skill match score.
    """
    # 1. Semantic Match
    semantic_score = calculate_semantic_similarity(resume_text, job_description)
    
    # 2. Skill Match
    matched, missing = check_missing_skills(resume_text, required_skills)
    total_skills = len(required_skills)
    
    if total_skills > 0:
        skill_score = (len(matched) / total_skills) * 100
    else:
        skill_score = 100.0 # No skills required, so 100% match on skills
        
    final_score = (semantic_score * weights['semantic']) + (skill_score * weights['skills'])
    
    # Classification
    # Classification
    if final_score >= 45:
        classification = 'SHORTLISTED'
    else:
        classification = 'REJECTED'

    return {
        'final_score': round(final_score, 2),
        'semantic_score': round(semantic_score, 2),
        'skill_score': round(skill_score, 2),
        'matched_skills': matched,
        'missing_skills': missing,
        'classification': classification
    }
