
import os
try:
    from PIL import Image, ImageDraw, ImageFont
    import pytesseract
except ImportError:
    print("PIL or pytesseract not installed")
    exit(1)

# Set tesseract path if not in PATH (common Windows paths)
tesseract_cmd_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    # Add other potential paths here if needed
]

# Check if tesseract is in PATH, if not try specific paths
if not pytesseract.pytesseract.tesseract_cmd or not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
    for path in tesseract_cmd_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"Used Tesseract at: {path}")
            
            # Check for data file in the same directory (flat install)
            data_dir = os.path.dirname(path)
            if os.path.exists(os.path.join(data_dir, 'eng.traineddata')):
                 print(f"Setting TESSDATA_PREFIX to: {data_dir}")
                 os.environ['TESSDATA_PREFIX'] = data_dir
                 os.environ['TESSDATA_PREFIX'] = os.path.join(data_dir, 'tessdata')
            
            # Fallback: Check user repo for tessdata
            repo_path = r'D:\jalak\Resume ATS Checker\ATS-Resume-Repo'
            if os.path.exists(os.path.join(repo_path, 'tessdata')):
                 print(f"Fallback: Setting TESSDATA_PREFIX to repo: {repo_path}")
                 os.environ['TESSDATA_PREFIX'] = repo_path

            break
else:
    print("Using Tesseract from PATH")

# Create a simple image with text
img = Image.new('RGB', (200, 100), color = (255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10,10), "Hello World", fill=(0,0,0))
img.save('test_ocr.png')

# Try to read it
try:
    text = pytesseract.image_to_string(Image.open('test_ocr.png'))
    print(f"Extracted Text: {text.strip()}")
    if "Hello World" in text:
        print("SUCCESS: OCR working")
    else:
        print("FAILURE: OCR ran but text did not match")
except Exception as e:
    print(f"FAILURE: {e}")
