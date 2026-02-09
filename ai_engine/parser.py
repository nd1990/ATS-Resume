import os
import re
from pdfminer.high_level import extract_text
import docx

def clean_text(text):
    """
    Removes extra whitespace and cleans up the text.
    """
    if not text:
        return ""
    # Replace multiple newlines/spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text_from_pdf(pdf_path):
    try:
        text = extract_text(pdf_path)
        return clean_text(text)
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def extract_text_from_docx(docx_path):
    try:
        doc = docx.Document(docx_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return clean_text('\n'.join(full_text))
    except Exception as e:
        print(f"Error reading DOCX {docx_path}: {e}")
        return ""


def extract_text_from_image(image_path):
    try:
        from PIL import Image
        import pytesseract

        # Set tesseract path if not in PATH (common Windows paths)
        tesseract_cmd_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'D:\jalak\Resume ATS Checker\ATS-Resume-Repo\tesseract.exe',
            # Add other potential paths here if needed
        ]
        
        # Check if tesseract is in PATH, if not try specific paths
        if not pytesseract.pytesseract.tesseract_cmd or not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
            for path in tesseract_cmd_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
        
        # Check for TESSDATA_PREFIX
        # If tesseract is installed in C:\Program Files but data is in D:\Repo\tessdata
        tessdata_paths = [
            r'D:\jalak\Resume ATS Checker\ATS-Resume-Repo\tessdata',
            r'C:\Program Files\Tesseract-OCR\tessdata',
            r'C:\Program Files (x86)\Tesseract-OCR\tessdata',
        ]
        
        # Only set if not already set or if default doesn't work (we assume it might not if we are here)
        if 'TESSDATA_PREFIX' not in os.environ:
             for path in tessdata_paths:
                 if os.path.exists(os.path.join(path, 'eng.traineddata')):
                     os.environ['TESSDATA_PREFIX'] = path
                     break
                 # Also check if it's in the root (flat install case)
                 elif os.path.exists(os.path.join(os.path.dirname(path), 'eng.traineddata')):
                      # os.path.dirname(path) would be e.g. C:\Program Files\Tesseract-OCR
                      # But wait, TESSDATA_PREFIX usually wants the parent of tessdata OR the folder itself?
                      # Let's stick to the folder containing .traineddata if possible, or tesseract specific quirk.
                      # We found earlier that pointing to the folder containing .traineddata works (path 2).
                      pass

        text = pytesseract.image_to_string(Image.open(image_path))
        return clean_text(text)
    except ImportError:
        print("Error: pytesseract or Pillow not installed.")
        return ""
    except Exception as e:
        print(f"Error reading Image {image_path}: {e}")
        return ""

def extract_resume_text(file_path):
    """
    Detects file type and extracts text accordingly.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    elif ext in ['.jpg', '.jpeg', '.png']:
        return extract_text_from_image(file_path)
    else:
        # TODO: Add .doc support if needed
        pass
    return ""

