try:
    import spacy
    print(f"Spacy version: {spacy.__version__}")
    print("Spacy imported successfully")
except ImportError as e:
    print(f"Spacy import failed: {e}")
except Exception as e:
    print(f"Spacy error: {e}")
