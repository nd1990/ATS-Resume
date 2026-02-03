try:
    import numpy
    print(f"Numpy version: {numpy.__version__}")
    print("Numpy imported successfully")
except ImportError as e:
    print(f"Numpy import failed: {e}")
except Exception as e:
    print(f"Numpy error: {e}")
