try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    print("Sklearn imported successfully")
except ImportError as e:
    print(f"Sklearn import failed: {e}")
except Exception as e:
    print(f"Sklearn error: {e}")
