try:
    import torch
    print(f"Torch version: {torch.__version__}")
    print("Torch imported successfully")
except ImportError as e:
    print(f"Torch import failed: {e}")
except Exception as e:
    print(f"Torch error: {e}")
