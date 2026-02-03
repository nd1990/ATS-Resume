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

def extract_resume_text(file_path):
    """
    Detects file type and extracts text accordingly.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    else:
        # TODO: Add .doc support if needed (requires different tools)
        pass
    return ""
