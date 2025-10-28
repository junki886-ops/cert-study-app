import pdfplumber
from pdf2image import convert_from_path
import pytesseract

# Windows: 설치 경로 지정 필요
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler-24.02.0\Library\bin"  # Poppler 설치 경로

def extract_page_text_with_fallback(pdf_path: str, dpi: int = 200):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""

            if txt.strip():
                results.append((i, "text", txt.strip()))
            else:
                images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1,
                                           poppler_path=POPPLER_PATH, dpi=dpi)
                if images:
                    ocr_txt = pytesseract.image_to_string(images[0], lang="kor+eng").strip()
                    results.append((i, "ocr", ocr_txt))
                else:
                    results.append((i, "ocr", ""))
    return results
