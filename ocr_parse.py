import os
import pytesseract
from pdf2image import convert_from_path

# 필요시 tesseract 경로 지정
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def parse_pdf(pdf_path, image_dir):
    """ PDF → 이미지 → OCR → 텍스트 → 문제 항목 추출 """
    os.makedirs(image_dir, exist_ok=True)
    pages = convert_from_path(pdf_path, dpi=200)
    items = []

    for idx, page in enumerate(pages):
        img_path = os.path.join(image_dir, f"page_{idx+1}.png")
        page.save(img_path, "PNG")

        text = pytesseract.image_to_string(page, lang="kor+eng")

        # --- 단순 규칙 예시 ---
        if "문제" in text:
            item = {
                "qno": f"{idx+1}",
                "stem": text.split("\n")[0],
                "options": [line for line in text.split("\n") if line.startswith(("①","②","③","④"))],
                "answer": "",
                "explanation": "",
                "category": None,
                "subcategory": None
            }
            items.append(item)

    return items
